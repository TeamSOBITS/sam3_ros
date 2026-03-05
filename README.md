<a name="readme-top"></a>

[EN](README.md) | [JA](README_ja.md)

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

# SAM3 ROS

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#overview">Overview</a>
    </li>
    <li>
      <a href="#setup">Setup</a>
      <ul>
        <li><a href="#environment">Environment</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#download-sam-3-weight-file">Download SAM 3 Weight File</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#parameters">Parameters</a></li>
    <li><a href="#demo">Demo</a></li>
     <!-- <li><a href="#milestone">Milestone</a></li> -->
    <li><a href="#references">References</a></li>
  </ol>
</details>

## Overview
`sam3_ros` is a wrapper package that enables the use of Meta’s Segment Anything Model 3 (SAM3) in ROS 2.

This package performs **promptable segmentation using text prompts**, providing the following features in a ROS 2 environment.

**Main Features:**
- Object segmentation via text instructions  
- Multi-class and multi-instance support  
- Bounding box output (Detection2D)  
- Detection with segmentation masks (Detection2DWithMask)  
- Visualization image output 

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Setup
This section explains how to set up this repository.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Environment

| System  | Version |
| ------------- | ------------- |
| Ubuntu | 22.04 (Jammy Jellyfish) |
| ROS | Humble Hawksbill |
| Python | 3.0~ |

### Installation
1. Move to your ROS 2 `src` directory.
   ```sh
   cd　~/colcon_ws/src/
   ```
2. Clone this repository.
   ```sh
   git clone -b humble-devel https://github.com/TeamSOBITS/sam3_ros.git
   ```
3. Navigate to this repository.
   ```sh
   cd sam3_ros
   ```
4. Install dependencies.
    ```sh
    bash install.sh
    ```
5. Build the package.
   ```sh
   cd ~/colcon_ws/
   colcon build --symlink-install
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Download SAM 3 Weight File
Due to licensing restrictions, the SAM 3 weight file (`sam3.pt`) is not downloaded automatically.
Therefore, you must **download it manually** in advance.

1. Visit the [**SAM 3 model page**](https://huggingface.co/facebook/sam3) on Hugging Face and request access to the model weights.

2. After approval, download [`sam3.pt`](https://huggingface.co/facebook/sam3/resolve/main/sam3.pt?download=true).

3. Place the downloaded `sam3.pt` file into the directory below.
   - Weight directory: （[`sam3_ros/weights`](https://github.com/TeamSOBITS/sam3_ros/blob/humble-devel/weights)）

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Usage
1. Launch your camera and modify **image_topic_name** in [sam3.launch.py](https://github.com/TeamSOBITS/sam3_ros/blob/humble-devel/launch/sam3.launch.py) to match your camera topic.
   
   Example:
   ```sh
   default_value="/camera/color/image_raw"              # orbbec_series
   ```
2. If using an RGB-D camera, also modify **point_cloud_topic** in [sam3.launch.py](https://github.com/TeamSOBITS/sam3_ros/blob/humble-devel/launch/sam3.launch.py).
   Example:
   ```sh
   default_value="/camera/depth_registered/points"     # orbbec_series
   ```
3. Place your prepared weight file into the [weights directory](https://github.com/TeamSOBITS/sam3_ros/blob/humble-devel/weights).
4. Update **weight_file** in [sam3.launch.py](https://github.com/TeamSOBITS/sam3_ros/blob/humble-devel/launch/sam3.launch.py)
   ```sh
   default_value=os.path.join(get_package_share_directory("sam3_ros"), "weights", "sam3.pt")
   ```
5. Rebuild the package.
   ```sh
   cd ~/colcon_ws/
   colcon build --symlink-install
   ```
6. Launch SAM 3.
    ```sh
    ros2 launch sam3_ros sam3.launch.py
    ```
7. Update prompt during runtime (without relaunch).
    ```sh
    # Single class
    ros2 topic pub --once /sam3_ros/set_prompt_text std_msgs/msg/String "{data: 'bottle'}"

    # Multiple classes (comma separated or list string)
    ros2 topic pub --once /sam3_ros/set_prompt_text std_msgs/msg/String "{data: 'bottle,cup,person'}"
    # ros2 topic pub --once /sam3_ros/set_prompt_text std_msgs/msg/String "{data: \"['bottle','cup','person']\"}"
    ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Parameters
The following parameters can be configured in [sam3.launch.py](https://github.com/TeamSOBITS/sam3_ros/blob/humble-devel/launch/sam3.launch.py).


| Parameter               | Description                                                                                                                     | Default    |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| weight_file             | SAM3 weight file                                                                                                                | sam3.pt    |
| prompt_text             | Target segmentation classes (string array)                                                                                      | ["object"] |
| threshold               | Mask confidence threshold                                                                                                       | 0.75       |
| half                    | Enable FP16 inference                                                                                                           | True       |
| image_show              | Enable Ultralytics visualization                                                                                                | False      |
| execute_default         | Enable inference on startup                                                                                                     | True       |
| use_3d                  | Enable 3D detection                                                                                                             | False      |
| cluster_tolerance       | Distance threshold for grouping point clouds into a single object. Larger values increase search range and slow processing.     | 0.01       |
| min_clusterSize         | Minimum number of points to be considered a valid object (smaller clusters are treated as noise).                               | 100        |
| max_clusterSize         | Maximum number of points allowed for one object (larger clusters are rejected as background, e.g., floor).                      | 20000      |
| noise_point_cloud_range | Amount of point cloud trimming in x/y/z to remove background surfaces (floor/walls). Excessive values may remove object points. | 0.01       |
| fast_shot               | Enable fast_shot                                                                                                                | true       |
| enable_id               | Append IDs to detected labels (e.g., apple_01)                                                                                  | false      |

<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Publications

| Topic                                   | Type                     | Description                  |
| --------------------------------------- | ------------------------ | ---------------------------- |
| `/sam3_ros/object_boxes`                | Detection2DArray         | Bounding boxes only          |
| `/sam3_ros/object_masks`                | DetectMaskArray          | Instance mask results        |
| `/sam3_ros/segmented_image`             | sensor_msgs/Image        | Visualization image          |

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Demo
| Object Detection | Object Recognition | Instance Segmentation |
|:---:|:---:|:---:|
| ![](docs/sam3_object_raw.png) | ![](docs/sam3_multiclass_raw.png) | ![](docs/sam3_instant_raw.png) |
| ![](docs/sam3_object_result.png) | ![](docs/sam3_multiclass_result.png) | ![](docs/sam3_instant_result.png) |

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## References
* [SAM 3: Segment Anything with Concepts](https://github.com/facebookresearch/sam3)
* [ Ultralytics Documentation](https://docs.ultralytics.com/models/sam-3/)

[contributors-shield]: https://img.shields.io/github/contributors/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[contributors-url]: https://github.com/TeamSOBITS/sam3_ros/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[forks-url]: https://github.com/TeamSOBITS/sam3_ros/network/members
[stars-shield]: https://img.shields.io/github/stars/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[stars-url]: https://github.com/TeamSOBITS/sam3_ros/stargazers
[issues-shield]: https://img.shields.io/github/issues/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[issues-url]: https://github.com/TeamSOBITS/sam3_ros/issues
[license-shield]: https://img.shields.io/github/license/TeamSOBITS/sam3_ros.svg?style=for-the-badge
[license-url]: LICENSE
