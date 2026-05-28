import ast
import gc
import os
import cv2
import numpy as np
import torch
from cv_bridge import CvBridge

import rclpy
from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSDurabilityPolicy, QoSReliabilityPolicy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn, LifecycleState
from rcl_interfaces.msg import SetParametersResult

from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from sobits_interfaces.msg import DetectMask, DetectMaskArray
from geometry_msgs.msg import Point, Quaternion

from ultralytics.models.sam import SAM3SemanticPredictor


class Sam3Node(LifecycleNode):

    _RELIABILITY_MAP = {
        "best_effort": QoSReliabilityPolicy.BEST_EFFORT,
        "reliable": QoSReliabilityPolicy.RELIABLE,
        "system_default": QoSReliabilityPolicy.SYSTEM_DEFAULT,
        "best_available": QoSReliabilityPolicy.BEST_AVAILABLE,
        "unknown": QoSReliabilityPolicy.UNKNOWN,
    }

    def __init__(self) -> None:
        super().__init__("sam3_ros")

        self.declare_parameter("weight_file", "sam3.pt")
        self.declare_parameter("auto_configure", True)
        self.declare_parameter("auto_activate", True)
        self.declare_parameter("threshold", 0.75)
        self.declare_parameter("half", True)
        self.declare_parameter("image_topic_name", "image_raw")
        self.declare_parameter("prompt_text", [""])
        self.declare_parameter("image_show", False)
        self.declare_parameter("inference_hz", 5.0)
        self.declare_parameter("publish_mask", True)
        self.declare_parameter("publish_mask_pixels", True)
        self.declare_parameter("publish_mask_image", True)
        self.declare_parameter("image_reliability", "best_effort")

        self.predictor = None
        self.sub = None
        self.inference_timer = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:

        self.predictor = None
        self.sub = None
        self.inference_timer = None

        self.weight_file = self.get_parameter("weight_file").value
        self.threshold = float(self.get_parameter("threshold").value)
        self.half = self.get_parameter("half").value
        self.image_topic = self.get_parameter("image_topic_name").value
        self.prompt_text = self.parse_prompt_text(
            self.get_parameter("prompt_text").value
        )
        self.image_show = self.get_parameter("image_show").value
        self.inference_hz = float(self.get_parameter("inference_hz").value)
        self.publish_mask = self.get_parameter("publish_mask").value
        self.publish_mask_pixels = self.get_parameter("publish_mask_pixels").value
        self.publish_mask_image = self.get_parameter("publish_mask_image").value
        self.image_reliability = self.get_parameter("image_reliability").value

        if not os.path.exists(self.weight_file):
            self.get_logger().warn(f"Weight file not found at configure time: {self.weight_file}")
        if not 0.0 < self.threshold <= 1.0:
            self.get_logger().error(f"threshold must be in (0.0, 1.0], got {self.threshold}")
            return TransitionCallbackReturn.FAILURE
        if not self.prompt_text:
            self.get_logger().error("prompt_text must not be empty")
            return TransitionCallbackReturn.FAILURE
        if self.inference_hz <= 0.0:
            self.get_logger().error(f"inference_hz must be > 0, got {self.inference_hz}")
            return TransitionCallbackReturn.FAILURE
        self.inference_hz = max(self.inference_hz, 0.1)

        if self.image_reliability not in self._RELIABILITY_MAP:
            self.get_logger().error(
                f"image_reliability must be one of {list(self._RELIABILITY_MAP)}, got '{self.image_reliability}'"
            )
            return TransitionCallbackReturn.FAILURE

        self.get_logger().info(f"Weight file: {self.weight_file}")
        self.get_logger().info(f"Threshold: {self.threshold}")
        self.get_logger().info(f"Half precision: {self.half}")
        self.get_logger().info(f"Image topic: {self.image_topic}")
        self.get_logger().info(f"Prompt text: {self.prompt_text}")
        self.get_logger().info(f"Image show: {self.image_show}")
        self.get_logger().info(f"Inference Hz: {self.inference_hz}")
        self.get_logger().info(f"Publish mask: {self.publish_mask}")
        self.get_logger().info(f"Publish mask pixels: {self.publish_mask_pixels}")
        self.get_logger().info(f"Publish mask image: {self.publish_mask_image}")
        self.get_logger().info(f"Image reliability: {self.image_reliability}")

        self.image_qos_profile = QoSProfile(
            reliability=self._RELIABILITY_MAP[self.image_reliability],
            history=QoSHistoryPolicy.KEEP_LAST,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=1,
        )
        self.pub_det = self.create_lifecycle_publisher(
            Detection2DArray, self.get_name() + "/object_boxes", 1
        )
        self.pub_mask = self.create_lifecycle_publisher(
            DetectMaskArray, self.get_name() + "/object_masks", 1
        )
        self.pub_img = self.create_lifecycle_publisher(
            Image, self.get_name() + "/detected_image", 1
        )

        self.bridge = CvBridge()
        self.latest_msg = None
        self.latest_stamp = None
        self.last_processed_stamp = None
        self.is_processing = False
        self.last_stamp = None
        self._param_cb = self.add_on_set_parameters_callback(self.on_parameter_update)

        super().on_configure(state)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:

        overrides = dict(
            conf=self.threshold,
            task="segment",
            mode="predict",
            model=self.weight_file,
            half=self.half,
            save=False,
            show=self.image_show,
            verbose=False,
        )
        try:
            self.predictor = SAM3SemanticPredictor(overrides=overrides)
            self.predictor.setup_model()
            self.get_logger().info(f"SAM3 model loaded: {self.weight_file} on {self.predictor.device}")
        except FileNotFoundError:
            predictor = getattr(self, "predictor", None)
            predictor_device = str(getattr(predictor, "device", ""))
            self.predictor = None
            if predictor is not None:
                del predictor
            if "cuda" in predictor_device:
                torch.cuda.empty_cache()
            gc.collect()
            self.get_logger().error(f"Model file '{self.weight_file}' does not exist")
            return TransitionCallbackReturn.ERROR
        except Exception as e:
            predictor = getattr(self, "predictor", None)
            predictor_device = str(getattr(predictor, "device", ""))
            self.predictor = None
            if predictor is not None:
                del predictor
            if "cuda" in predictor_device:
                torch.cuda.empty_cache()
            gc.collect()
            self.get_logger().error(f"Failed to load SAM3 model: {e}")
            return TransitionCallbackReturn.ERROR

        self.sub = self.create_subscription(
            Image, self.image_topic, self.image_cb, self.image_qos_profile
        )
        self.inference_timer = self.create_timer(
            1.0 / self.inference_hz,
            self.inference_timer_cb,
        )

        super().on_activate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        predictor = getattr(self, "predictor", None)
        predictor_device = str(getattr(predictor, "device", ""))
        if predictor is not None:
            del self.predictor
            self.predictor = None

        if "cuda" in predictor_device:
            self.get_logger().info("Clearing CUDA cache")
            torch.cuda.empty_cache()
        gc.collect()

        sub = getattr(self, "sub", None)
        if sub is not None:
            self.destroy_subscription(sub)
            self.sub = None
        inference_timer = getattr(self, "inference_timer", None)
        if inference_timer is not None:
            self.destroy_timer(inference_timer)
            self.inference_timer = None

        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_parameter_update(self, params) -> SetParametersResult:
        try:
            for param in params:
                if param.name == "weight_file":
                    if self._state_machine.current_state[1] == "active":
                        return SetParametersResult(successful=False, reason="weight_file cannot be changed while active; deactivate first")
                    new_path = str(param.value)
                    if not os.path.exists(new_path):
                        return SetParametersResult(successful=False, reason=f"Weight file not found: {new_path}")
                    self.weight_file = new_path
                    self.get_logger().info(f"Updated weight_file: {self.weight_file}")
                elif param.name == "threshold":
                    value = float(param.value)
                    if not 0.0 < value <= 1.0:
                        return SetParametersResult(successful=False, reason="threshold must be in (0.0, 1.0]")
                    self.threshold = value
                    if self.predictor is not None:
                        self.predictor.args.conf = self.threshold
                    self.get_logger().info(f"Updated threshold: {self.threshold}")
                elif param.name == "prompt_text":
                    parsed = self.parse_prompt_text(param.value)
                    if not parsed:
                        return SetParametersResult(successful=False, reason="prompt_text must not be empty")
                    self.prompt_text = parsed
                    self.get_logger().info(f"Updated prompt_text: {self.prompt_text}")
                elif param.name == "inference_hz":
                    value = float(param.value)
                    if value <= 0.0:
                        return SetParametersResult(successful=False, reason="inference_hz must be > 0")
                    self.inference_hz = max(value, 0.1)
                    if hasattr(self, "inference_timer") and self.inference_timer is not None:
                        self.destroy_timer(self.inference_timer)
                        self.inference_timer = self.create_timer(
                            1.0 / self.inference_hz,
                            self.inference_timer_cb,
                        )
                    self.get_logger().info(f"Updated inference_hz: {self.inference_hz}")
                elif param.name == "publish_mask":
                    self.publish_mask = bool(param.value)
                    self.get_logger().info(f"Updated publish_mask: {self.publish_mask}")
                elif param.name == "publish_mask_pixels":
                    self.publish_mask_pixels = bool(param.value)
                    self.get_logger().info(f"Updated publish_mask_pixels: {self.publish_mask_pixels}")
                elif param.name == "publish_mask_image":
                    self.publish_mask_image = bool(param.value)
                    self.get_logger().info(f"Updated publish_mask_image: {self.publish_mask_image}")
                elif param.name == "image_reliability":
                    if self._state_machine.current_state[1] == "active":
                        return SetParametersResult(successful=False, reason="image_reliability cannot be changed while active; deactivate first")
                    value = str(param.value)
                    if value not in self._RELIABILITY_MAP:
                        return SetParametersResult(
                            successful=False,
                            reason=f"image_reliability must be one of {list(self._RELIABILITY_MAP)}",
                        )
                    self.image_reliability = value
                    self.image_qos_profile.reliability = self._RELIABILITY_MAP[value]
                    self.get_logger().info(f"Updated image_reliability: {self.image_reliability}")
        except Exception as e:
            return SetParametersResult(successful=False, reason=str(e))

        return SetParametersResult(successful=True)

    def image_cb(self, msg: Image) -> None:
        self.latest_msg = msg
        self.latest_stamp = msg.header.stamp

    def inference_timer_cb(self) -> None:
        if self.predictor is None:
            return
        if self.latest_msg is None:
            self.get_logger().warn(
                f"Waiting for image on '{self.image_topic}'",
                throttle_duration_sec=10.0,
            )
            return
        if self.latest_stamp == self.last_processed_stamp:
            return
        if self.is_processing:
            return

        self.is_processing = True
        msg = self.latest_msg
        stamp = self.latest_stamp
        try:
            self.process_image(msg)
        except Exception as e:
            self.get_logger().error(f"SAM3 inference failed: {e}")
        finally:
            self.last_processed_stamp = stamp
            self.is_processing = False

    def process_image(self, msg: Image) -> None:

        encoding = msg.encoding
        cv_image = self.bridge.imgmsg_to_cv2(msg)

        if encoding == 'bgr8':
            pass
        elif encoding == 'bgra8':
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGRA2BGR)
        elif encoding == 'rgba8':
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGBA2BGR)
        elif encoding == 'rgb8':
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
        else:
            self.get_logger().error(f"Unsupported encoding: {encoding}")
            return

        if self.last_stamp is None or msg.header.stamp != self.last_stamp:
            self.predictor.set_image(cv_image)
            self.last_stamp = msg.header.stamp

        det_boxes = Detection2DArray()
        det_boxes.header = msg.header

        mask_array = DetectMaskArray()
        mask_array.header = msg.header

        overlay = cv_image.copy()
        instance_id = 0

        for class_name in self.prompt_text:

            results = self.predictor(text=[class_name])
            if results is None or len(results) == 0:
                continue

            res = results[0]
            if res.masks is None:
                continue

            color = self.get_color_for_class(class_name)

            for mask in res.masks.data:

                mask_np = mask.cpu().numpy().astype(bool)
                if not mask_np.any():
                    continue

                ys, xs = np.where(mask_np)
                x, y, w, h = cv2.boundingRect(np.column_stack((xs, ys)))

                if self.publish_mask:
                    mask_msg = DetectMask()
                    mask_msg.instance_id = f"{class_name}_{instance_id}"

                    if self.publish_mask_pixels:
                        mask_msg.pixel_x = xs.tolist()
                        mask_msg.pixel_y = ys.tolist()

                    if self.publish_mask_image:
                        binary_mask = (mask_np * 255).astype(np.uint8)
                        mask_msg.mask = self.bridge.cv2_to_imgmsg(binary_mask, encoding="mono8")
                        mask_msg.mask.header = msg.header

                    ohwp_mask = ObjectHypothesisWithPose()
                    ohwp_mask.hypothesis.class_id = class_name
                    ohwp_mask.hypothesis.score = 1.0
                    mask_msg.results.append(ohwp_mask)
                    mask_array.masks.append(mask_msg)

                det2d = Detection2D()
                det2d.header = msg.header
                det2d.id = f"{class_name}_{instance_id}"

                det2d.bbox.center.position.x = float(x + w / 2.0)
                det2d.bbox.center.position.y = float(y + h / 2.0)
                det2d.bbox.size_x = float(w)
                det2d.bbox.size_y = float(h)

                ohwp = ObjectHypothesisWithPose()
                det2d.results.append(ohwp)
                ohwp.hypothesis.class_id = class_name

                ohwp.pose.pose.position = Point(
                    x=det2d.bbox.center.position.x,
                    y=det2d.bbox.center.position.y,
                    z=-1.0
                )
                ohwp.pose.pose.orientation = Quaternion(w=1.0)

                det_boxes.detections.append(det2d)

                overlay[mask_np] = (
                    0.6 * overlay[mask_np] + 0.4 * np.array(color)
                ).astype(np.uint8)

                x1 = int(x)
                y1 = int(y)
                x2 = int(x + w)
                y2 = int(y + h)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)

                label = f"{class_name} #{instance_id}"
                cv2.putText(
                    overlay,
                    label,
                    (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                    cv2.LINE_AA,
                )

                instance_id += 1

        if self.publish_mask:
            self.pub_mask.publish(mask_array)
        self.pub_det.publish(det_boxes)
        self.pub_img.publish(
            self.bridge.cv2_to_imgmsg(overlay, "bgr8")
        )

    def parse_prompt_text(self, raw_value):
        if isinstance(raw_value, list):
            return [str(v).strip() for v in raw_value if str(v).strip()]
        if isinstance(raw_value, str):
            value = raw_value.strip()
            if not value:
                return []
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except (ValueError, SyntaxError):
                pass
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                items = []
                for token in inner.split(","):
                    cleaned = token.strip().strip("'\"")
                    if cleaned:
                        items.append(cleaned)
                if items:
                    return items
            if "," in value:
                return [v.strip() for v in value.split(",") if v.strip()]
            return [value]
        return []

    def get_color_for_class(self, name: str):
        """Deterministic color from class name"""
        rng = abs(hash(name)) % (256**3)
        return ((rng >> 16) & 255, (rng >> 8) & 255, rng & 255)


def main(args=None):
    rclpy.init(args=args)
    node = Sam3Node()

    auto_configure = node.get_parameter("auto_configure").value
    auto_activate = node.get_parameter("auto_activate").value

    configure_succeeded = True
    if auto_configure or auto_activate:
        configure_result = node.trigger_configure()
        configure_succeeded = configure_result == TransitionCallbackReturn.SUCCESS
    if auto_activate:
        if configure_succeeded:
            node.trigger_activate()
        else:
            node.get_logger().error(
                "Auto-activation requested, but node configuration failed; "
                "skipping activation."
            )

    node.get_logger().info("SAM3 Node started. Spinning...")

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
