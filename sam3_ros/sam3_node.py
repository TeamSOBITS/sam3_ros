import cv2
import numpy as np
from cv_bridge import CvBridge

import rclpy
from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSDurabilityPolicy, QoSReliabilityPolicy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn, LifecycleState
from rclpy.qos import QoSProfile, QoSReliabilityPolicy

from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from sobits_interfaces.msg import Detection2DWithMask, Detection2DWithMaskArray
from geometry_msgs.msg import Point, Quaternion
from std_srvs.srv import SetBool

from ultralytics.models.sam import SAM3SemanticPredictor


class Sam3Node(LifecycleNode):

    def __init__(self) -> None:
        super().__init__("sam3_ros")

        self.declare_parameter("weight_file", "sam3.pt")
        self.declare_parameter("threshold", 0.75)
        self.declare_parameter("half", True)                        # Use FP16 for faster inference
        self.declare_parameter("image_topic_name", "image_raw")
        self.declare_parameter("prompt_text", ["object"])
        self.declare_parameter("execute_default", True)
        self.declare_parameter("image_show", False)

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
    
        self.weight_file = self.get_parameter("weight_file").value
        self.threshold = self.get_parameter("threshold").value
        self.half = self.get_parameter("half").value
        self.image_topic = self.get_parameter("image_topic_name").value
        self.prompt_text = list(self.get_parameter("prompt_text").value)
        self.enable = self.get_parameter("execute_default").value
        self.image_show = self.get_parameter("image_show").value

        self.image_qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=1,
        )
        self.pub_det = self.create_lifecycle_publisher(
            Detection2DArray, "object_boxes", 1
        )
        self.pub_det_mask = self.create_lifecycle_publisher(
            Detection2DWithMaskArray, "object_detections_with_mask", 1
        )
        self.pub_img = self.create_lifecycle_publisher(
            Image, "segmented_image", 1
        )

        self.bridge = CvBridge()
        self.last_stamp = None

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
        )
        self.predictor = SAM3SemanticPredictor(overrides=overrides)

        self.sub = self.create_subscription(
            Image, self.image_topic, self.image_cb, self.image_qos_profile
        )
        self.srv = self.create_service(SetBool, "run_ctrl", self.enable_cb)

        super().on_activate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        del self.predictor
        self.predictor = None
        self.destroy_subscription(self.sub)
        self.destroy_service(self.srv)
        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def enable_cb(self, request: SetBool.Request, response: SetBool.Response) -> SetBool.Response:
        self.enable = request.data
        response.success = True
        return response

    def image_cb(self, msg: Image) -> None:

        if not self.enable:
            return

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

        det_array = Detection2DWithMaskArray()
        det_array.header = msg.header

        det_boxes = Detection2DArray()
        det_boxes.header = msg.header

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


                # -----------------------------
                # Detection2DWithMask
                # -----------------------------
                det = Detection2DWithMask()
                det.header = msg.header
                det.instance_id = instance_id
                det.class_id = class_name

                det.bbox.center.position.x = float(x + w / 2.0)
                det.bbox.center.position.y = float(y + h / 2.0)
                det.bbox.size_x = float(w)
                det.bbox.size_y = float(h)

                det.hypothesis.hypothesis.class_id = class_name

                det.hypothesis.pose.pose.position = Point(
                    x=det.bbox.center.position.x,
                    y=det.bbox.center.position.y,
                    z=-1.0
                )
                det.hypothesis.pose.pose.orientation = Quaternion(w=1.0)

                binary_mask = (mask_np * 255).astype(np.uint8)
                det.mask = self.bridge.cv2_to_imgmsg(binary_mask, encoding="mono8")
                det.mask.header = msg.header

                det_array.detections.append(det)


                # -----------------------------
                # Detection2D (no mask)
                # -----------------------------
                det2d = Detection2D()
                det2d.header = msg.header
                det2d.id = f"{class_name}_{instance_id}"

                det2d.bbox.center.position.x = det.bbox.center.position.x
                det2d.bbox.center.position.y = det.bbox.center.position.y
                det2d.bbox.size_x = det.bbox.size_x
                det2d.bbox.size_y = det.bbox.size_y

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


                # -----------------------------
                # Visualization
                # -----------------------------
                # Overlay mask on image
                overlay[mask_np] = (
                    0.6 * overlay[mask_np] + 0.4 * np.array(color)
                ).astype(np.uint8)

                # Draw bounding box
                x1 = int(x)
                y1 = int(y)
                x2 = int(x + w)
                y2 = int(y + h)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)

                # Draw label
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

        self.pub_det_mask.publish(det_array)
        self.pub_det.publish(det_boxes)
        self.pub_img.publish(
            self.bridge.cv2_to_imgmsg(overlay, "bgr8")
        )

    def get_color_for_class(self, name: str):
        """Deterministic color from class name"""
        rng = abs(hash(name)) % (256**3)
        return ((rng >> 16) & 255, (rng >> 8) & 255, rng & 255)

def main(args=None):
    rclpy.init(args=args)
    node = Sam3Node()
    node.trigger_configure()
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
