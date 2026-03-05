import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.conditions import IfCondition


def generate_launch_description():
    image_topic_name = LaunchConfiguration("image_topic_name")
    point_cloud_topic = LaunchConfiguration("point_cloud_topic")
    depth_image_topic_name = LaunchConfiguration("depth_image_topic_name")
    info_topic_name = LaunchConfiguration("info_topic_name")
    positioning_detection_mode_object = LaunchConfiguration("positioning_detection_mode_object")
    weight_file = LaunchConfiguration("weight_file")
    execute_default = LaunchConfiguration("execute_default")
    image_show = LaunchConfiguration("image_show")
    threshold = LaunchConfiguration("threshold")
    prompt_text = LaunchConfiguration("prompt_text")
    half = LaunchConfiguration("half")
    publish_mask = LaunchConfiguration("publish_mask")
    publish_mask_pixels = LaunchConfiguration("publish_mask_pixels")
    publish_mask_image = LaunchConfiguration("publish_mask_image")
    namespace = LaunchConfiguration("namespace")
    base_frame_name = LaunchConfiguration("base_frame_name")
    use_3d = LaunchConfiguration("use_3d")

    launch_args = [
        DeclareLaunchArgument(
            "image_topic_name",
            description="ROS Topic Name of sensor_msgs/msg/Image message. (sensor_msgs/msg/Image)",
            default_value="/camera/color/image_raw",                ## realsense
            # default_value="/rgb/image_raw",                       ## azure_kinect
            # default_value="/camera/color/image_raw",              ## orbbec_series
            # default_value="/camera/rgb/image_raw",                ## xtion
        ),
        DeclareLaunchArgument(
            "point_cloud_topic",
            description="Detection 3D Pose from 2D Pose (sensor_msgs/msg/PointCloud2). if you select the 'point_cloud' in 'positioning_detection_mode'.",
            default_value="/camera/depth/color/points",             ## realsense
            # default_value="/points2",                             ## azure_kinect
            # default_value="/camera/depth_registered/points",      ## orbbec_series
            # default_value="/camera/depth_registered/points",      ## xtion
        ),
        DeclareLaunchArgument(
            "depth_image_topic_name",
            description="Detection 3D Pose from 2D Pose (sensor_msgs/msg/Image). if you select the 'depth_image' in 'positioning_detection_mode'.",
            default_value="/camera/depth/image_rect_raw",           ## realsense
            # default_value="/depth_to_rgb/image_raw",              ## azure_kinect
            # default_value="",                                     ## orbbec_series
            # default_value="/camera/depth/image_raw",              ## xtion
        ),
        DeclareLaunchArgument(
            "info_topic_name",
            description="Setup the camera info topic name. (sensor_msgs/msg/CameraInfo)",
            default_value="/camera/color/camera_info",              ## realsense
            # default_value="/rgb/camera_info",                     ## azure_kinect
            # default_value="",                                     ## orbbec_series
            # default_value="/camera/rgb/camera_info",              ## xtion
        ),
        DeclareLaunchArgument(
            "positioning_detection_mode_object",
            description="Select the 3D Pose Detection mode. Choose of ['point_cloud', 'fast_point', 'depth_image']",
            default_value="point_cloud",
        ),
        DeclareLaunchArgument(
            "weight_file",
            default_value=os.path.join(get_package_share_directory("sam3_ros"), "weights", "sam3.pt"),
            description="Weight file path",
        ),
        DeclareLaunchArgument(
            "execute_default",
            default_value="True",
            description="Whether to start SAM 3 enabled",
        ),
        DeclareLaunchArgument(
            "image_show",
            default_value="False",
            description="Flag to show image with predictions",
        ),
        DeclareLaunchArgument(
            "threshold",
            default_value="0.75",
            description="Minimum probability of a detection to be published",
        ),
        DeclareLaunchArgument(
            "prompt_text",
            default_value="['object']",
            # default_value="['object on the table']",
            # default_value="['metal cup', 'banana', 'pen', 'paper cup', 'headphone', 'dice', 'pringles potato chips', 'game controller']",
            # default_value="['red object']",
            description="Text prompt list for SAM3",
        ),
        DeclareLaunchArgument(
            "half",
            default_value="True",
            description="Use FP16 inference",
        ),
        DeclareLaunchArgument(
            "publish_mask",
            default_value="False",
            description="Publish object_masks topic (DetectMaskArray)",
        ),
        DeclareLaunchArgument(
            "publish_mask_pixels",
            default_value="False",
            description="Publish mask coordinates (pixel_x/pixel_y)",
        ),
        DeclareLaunchArgument(
            "publish_mask_image",
            default_value="False",
            description="Publish mask image field in DetectMask",
        ),
        DeclareLaunchArgument(
            "namespace",
            default_value="sam3_ros",
            description="Namespace for the nodes",
        ),
        DeclareLaunchArgument(
            "base_frame_name",
            default_value="base_footprint",
            description="Base frame name for TF and 3D detection",
        ),
        DeclareLaunchArgument(
            "use_3d",
            default_value="True",
            description="Whether to activate 3D detections",
        ),
    ]

    sam3_node_cmd = Node(
        package="sam3_ros",
        executable="sam3_node",
        name="sam3_node",
        namespace=namespace,
        parameters=[
            {
                "weight_file": weight_file,
                "execute_default": execute_default,
                "image_topic_name": image_topic_name,
                "threshold": threshold,
                "half": half,
                "image_show": image_show,
                "prompt_text": prompt_text,
                "publish_mask": publish_mask,
                "publish_mask_pixels": publish_mask_pixels,
                "publish_mask_image": publish_mask_image,
            },
        ],
        output="screen"
    )

    bbox_to_3d_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("image_to_position"),
                "launch",
                "bbox_to_3d.launch.py",
            )
        ),
        launch_arguments={
            "namespace": namespace,
            "base_frame_name": base_frame_name,
            "bbox_topic_name": "/sam3_ros/object_boxes",
            "cloud_topic_name": point_cloud_topic,
            "depth_image_topic_name": depth_image_topic_name,
            "info_topic_name": info_topic_name,
            "execute_default": execute_default,
            "cluster_tolerance": "0.01",
            "min_clusterSize": "200",
            "max_clusterSize": "20000",
            "noise_point_cloud_range": "0.03",
            "enable_id": "False",
            "positioning_detection_mode": positioning_detection_mode_object,
        }.items(),
        condition=IfCondition(use_3d),
    )

    return LaunchDescription(
        launch_args + [
            sam3_node_cmd,
            bbox_to_3d_cmd,
        ]
    )
