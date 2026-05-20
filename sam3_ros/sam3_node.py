import ast
import os
import cv2
import numpy as np
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

    def __init__(self) -> None:
        super().__init__("sam3_ros")

        self.declare_parameter("weight_file", "sam3.pt")
        self.declare_parameter("auto_configure_2d", True)
        self.declare_parameter("auto_activate_2d", True)
        self.declare_parameter("threshold", 0.75)
        self.declare_parameter("half", True)
        self.declare_parameter("image_topic_name", "image_raw")
        self.declare_parameter("prompt_text", ["object"])
        self.declare_parameter("image_show", False)
        self.declare_parameter("inference_hz", 5.0)
        self.declare_parameter("publish_mask", True)
        self.declare_parameter("publish_mask_pixels", True)
        self.declare_parameter("publish_mask_image", True)

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:

        self.weight_file = self.get_parameter("weight_file").value
        self.threshold = self.get_parameter("threshold").value
        self.half = self.get_parameter("half").value
        self.image_topic = self.get_parameter("image_topic_name").value
        self.prompt_text = self.parse_prompt_text(
            self.get_parameter("prompt_text").value
        )
        self.image_show = self.get_parameter("image_show").value
        self.inference_hz = max(float(self.get_parameter("inference_hz").value), 0.1)
        self.publish_mask = self.get_parameter("publish_mask").value
        self.publish_mask_pixels = self.get_parameter("publish_mask_pixels").value
        self.publish_mask_image = self.get_parameter("publish_mask_image").value

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

        self.image_qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
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
        self.model_error_reported = False
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
        self.predictor = SAM3SemanticPredictor(overrides=overrides)

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
        del self.predictor
        self.predictor = None
        self.destroy_subscription(self.sub)
        self.destroy_timer(self.inference_timer)
        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_parameter_update(self, params) -> SetParametersResult:
        try:
            for param in params:
                if param.name == "prompt_text":
                    self.prompt_text = self.parse_prompt_text(param.value)
                    self.get_logger().info(f"Updated prompt_text: {self.prompt_text}")
                elif param.name == "inference_hz":
                    self.inference_hz = max(float(param.value), 0.1)
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
        except Exception as e:
            return SetParametersResult(successful=False, reason=str(e))

        return SetParametersResult(successful=True)

    def image_cb(self, msg: Image) -> None:
        self.latest_msg = msg
        self.latest_stamp = msg.header.stamp

    def inference_timer_cb(self) -> None:
        if not os.path.exists(self.weight_file):
            if not self.model_error_reported:
                self.get_logger().error(
                    f"SAM3 weight file not found: {self.weight_file}. "
                    "Inference is disabled until a valid weight_file is set."
                )
                self.model_error_reported = True
            return
        if self.latest_msg is None:
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
            return [str(v) for v in raw_value]
        if isinstance(raw_value, str):
            value = raw_value.strip()
            if not value:
                return ["object"]
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
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
        return ["object"]

    def get_color_for_class(self, name: str):
        """Deterministic color from class name"""
        rng = abs(hash(name)) % (256**3)
        return ((rng >> 16) & 255, (rng >> 8) & 255, rng & 255)


def main(args=None):
    rclpy.init(args=args)
    node = Sam3Node()

    auto_configure_2d = node.get_parameter("auto_configure_2d").value
    auto_activate_2d = node.get_parameter("auto_activate_2d").value

    if auto_configure_2d or auto_activate_2d:
        node.trigger_configure()
    if auto_activate_2d:
        node.trigger_activate()

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
