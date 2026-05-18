import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, AndSubstitution
from launch_ros.actions import Node
from launch.conditions import IfCondition


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    image_topic_name = LaunchConfiguration("image_topic_name")
    weight_file = LaunchConfiguration("weight_file")
    execute_default = LaunchConfiguration("execute_default")
    image_show = LaunchConfiguration("image_show")
    threshold = LaunchConfiguration("threshold")
    prompt_text = LaunchConfiguration("prompt_text")
    inference_hz = LaunchConfiguration("inference_hz")
    half = LaunchConfiguration("half")
    publish_mask = LaunchConfiguration("publish_mask")
    publish_mask_pixels = LaunchConfiguration("publish_mask_pixels")
    publish_mask_image = LaunchConfiguration("publish_mask_image")
    namespace = LaunchConfiguration("namespace")
    bbox_to_3d_params_file = LaunchConfiguration("bbox_to_3d_params_file")
    mask_to_3d_params_file = LaunchConfiguration("mask_to_3d_params_file")
    use_bbox_to_3d = LaunchConfiguration("use_bbox_to_3d")
    use_mask_to_3d = LaunchConfiguration("use_mask_to_3d")

    launch_args = [
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="False",
            description="Use simulation clock.",
        ),
        DeclareLaunchArgument(
            "image_topic_name",
            description="ROS Topic Name of sensor_msgs/msg/Image message. (sensor_msgs/msg/Image)",
            default_value="camera/color/image_raw",                ## realsense
            # default_value="rgb/image_raw",                       ## azure_kinect
            # default_value="camera/color/image_raw",              ## orbbec_series
            # default_value="camera/rgb/image_raw",                ## xtion
        ),
        DeclareLaunchArgument(
            "positioning_detection_mode_object",
            description="Select the 3D Pose Detection mode. Choose of ['point_cloud', 'fast_point', 'depth_image']",
            default_value="point_cloud",
        ),
        DeclareLaunchArgument(
            "weight_file",
            default_value=os.path.join(
                get_package_share_directory("sam3_ros"), 
                "weights", 
                "sam3.pt" # "sam3.pt" or "sam3.1_multiplex.pt"
            ),
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
            "inference_hz",
            default_value="12.0",
            description="SAM3 inference rate in Hz (process latest frame by timer)",
        ),
        DeclareLaunchArgument(
            "half",
            default_value="False",
            description="Use FP16 inference (only enable if CUDA is available)",
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
            default_value="",
            description="Namespace for the nodes",
        ),
        DeclareLaunchArgument(
            "bbox_to_3d_params_file",
            default_value=os.path.join(
                get_package_share_directory("image_to_position"),
                "config",
                "bbox_to_3d.yaml",
            ),
            description="Parameter file path for bbox_to_3d",
        ),
        DeclareLaunchArgument(
            "mask_to_3d_params_file",
            default_value=os.path.join(
                get_package_share_directory("image_to_position"),
                "config",
                "mask_to_3d.yaml",
            ),
            description="Parameter file path for mask_to_3d",
        ),
        DeclareLaunchArgument(
            "use_bbox_to_3d",
            default_value="True",
            description="Whether to launch bbox_to_3d",
        ),
        DeclareLaunchArgument(
            "use_mask_to_3d",
            default_value="False",
             description="Whether to launch mask_to_3d (requires publish_mask to be True)",
        ),
    ]

    sam3_node_cmd = Node(
        package="sam3_ros",
        executable="sam3_node",
        name="sam3_ros",
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
                "inference_hz": inference_hz,
                "publish_mask": publish_mask,
                "publish_mask_pixels": publish_mask_pixels,
                "publish_mask_image": publish_mask_image,
                "use_sim_time": use_sim_time,
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
            "params_file": bbox_to_3d_params_file,
            "execute_default": execute_default,
        }.items(),
        condition=IfCondition(use_bbox_to_3d),
    )

    mask_to_3d_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("image_to_position"),
                "launch",
                "mask_to_3d.launch.py",
            )
        ),
        launch_arguments={
            "namespace": namespace,
            "params_file": mask_to_3d_params_file,
            "execute_default": execute_default,
        }.items(),
        condition=IfCondition(AndSubstitution(publish_mask, use_mask_to_3d)),
    )

    return LaunchDescription(
        launch_args + [
            sam3_node_cmd,
            bbox_to_3d_cmd,
            mask_to_3d_cmd,
        ]
    )
