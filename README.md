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
        <li><a href="#download-sam3-weight-file">Download SAM3 Weight File</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#parameters">Parameters</a></li>
    <li><a href="#topics">Topics</a></li>
    <li><a href="#demo">Demo</a></li>
    <li><a href="#references">References</a></li>
  </ol>
</details>

## Overview
`sam3_ros` is a ROS 2 lifecycle wrapper for Meta's Segment Anything Model 3 (SAM3).

It performs **promptable instance segmentation using text prompts** and exposes the results as standard ROS 2 messages.

**Main Features:**
- Text-prompted object segmentation (single and multi-class)
- Per-instance bounding box output (`Detection2DArray`)
- Per-instance mask output (`DetectMaskArray`) with optional pixel coordinates and mask image
- Annotated visualization image output
- Timer-driven inference loop decoupled from the image subscription
- Full ROS 2 lifecycle support (`configure` → `activate` → `deactivate` → `cleanup`)
- All parameters configurable at runtime via `ros2 param set`

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Setup

<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Environment

| System | Version |
| ------ | ------- |
| Ubuntu | 24.04 (Noble Numbat) |
| ROS 2  | Jazzy Jalisco |
| Python | 3.12 |

### Installation
1. Move to your ROS 2 `src` directory.
   ```sh
   cd ~/colcon_ws/src/
   ```
2. Clone this repository.
   ```sh
   git clone https://github.com/TeamSOBITS/sam3_ros.git
   ```
3. Navigate into the repository and install dependencies.
   ```sh
   cd sam3_ros/
   bash install.sh
   ```
4. Build the package.
   ```sh
   cd ~/colcon_ws/
   colcon build --symlink-install
   source install/setup.bash
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Download SAM3 Weight File
Two checkpoints are available: `sam3.pt` (SAM3) and `sam3.1_multiplex.pt` (SAM3.1).

Weight files are not downloaded automatically due to licensing restrictions.
Please **download the checkpoint manually** before launching the node.

1. Visit the [**SAM3 model page**](https://huggingface.co/facebook/sam3) or the [**SAM3.1 model page**](https://huggingface.co/facebook/sam3.1) on Hugging Face and request access.

2. After approval, download [`sam3.pt`](https://huggingface.co/facebook/sam3/resolve/main/sam3.pt?download=true) and/or [`sam3.1_multiplex.pt`](https://huggingface.co/facebook/sam3.1/resolve/main/sam3.1_multiplex.pt?download=true).

3. Place the downloaded file in the weights directory:
   ```
   sam3_ros/weights/
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Usage

1. Launch your camera and set `image_topic_name` to match your camera topic:
   ```sh
   ros2 launch sam3_ros sam3.launch.py image_topic_name:=/camera/color/image_raw
   ```

2. Launch with auto configure and activate:
   ```sh
   ros2 launch sam3_ros sam3.launch.py auto_configure_2d:=true auto_activate_2d:=true
   ```

3. Or manage the lifecycle manually:
   ```sh
   ros2 launch sam3_ros sam3.launch.py
   ros2 lifecycle set /sam3_node configure
   ros2 lifecycle set /sam3_node activate
   ```

4. Update the text prompt at runtime without restarting:
   ```sh
   ros2 param set /sam3_node prompt_text "['chair', 'table']"
   ```

5. Deactivate, cleanup, and reconfigure with a different model:
   ```sh
   ros2 lifecycle set /sam3_node deactivate
   ros2 lifecycle set /sam3_node cleanup
   ros2 param set /sam3_node weight_file sam3.1_multiplex.pt
   ros2 lifecycle set /sam3_node configure
   ros2 lifecycle set /sam3_node activate
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Parameters

The following parameters can be set via the launch file or `ros2 param set` at runtime.

| Parameter             | Description                                                                                   | Default                        | Runtime update |
| --------------------- | --------------------------------------------------------------------------------------------- | ------------------------------ | -------------- |
| `weight_file`         | SAM3 weight filename                                                                          | `sam3.pt`                      | cleanup first  |
| `weights_path`        | Directory containing the weight file                                                          | `<package>/weights`            | cleanup first  |
| `prompt_text`         | Text prompt list for segmentation (string array)                                              | `['']`                         | yes            |
| `threshold`           | Mask confidence threshold (0.0, 1.0]                                                          | `0.75`                         | yes            |
| `inference_hz`        | Inference rate in Hz (timer-driven, processes latest frame)                                   | `5.0`                          | yes            |
| `half`                | Enable FP16 inference (requires CUDA)                                                         | `true`                         | no             |
| `image_show`          | Enable Ultralytics built-in visualization window                                              | `false`                        | no             |
| `publish_mask`        | Publish `object_masks` topic (`DetectMaskArray`)                                              | `false`                        | yes            |
| `publish_mask_pixels` | Include pixel coordinate lists (`pixel_x`/`pixel_y`) in each mask                            | `false`                        | yes            |
| `publish_mask_image`  | Include binary mask image field in each `DetectMask`                                          | `false`                        | yes            |
| `image_reliability`   | QoS reliability for the image subscription (`best_effort`, `reliable`, `system_default`, ...) | `best_effort`                  | inactive only  |
| `device`              | Inference device (`cuda`, `cpu`, `cuda:0`, ...)                                               | `cuda` if available else `cpu` | no             |
| `auto_configure_2d`   | Configure the SAM3 lifecycle node on startup                                                  | `false`                        | —              |
| `auto_activate_2d`    | Activate the SAM3 lifecycle node on startup                                                   | `false`                        | —              |
| `auto_configure_3d`   | Configure the image_to_position lifecycle node on startup                                     | `false`                        | —              |
| `auto_activate_3d`    | Activate the image_to_position lifecycle node on startup                                      | `false`                        | —              |
| `use_bbox_to_3d`      | Launch the `bbox_to_3d` 3D detection pipeline                                                 | `false`                        | —              |
| `use_mask_to_3d`      | Launch the `mask_to_3d` pipeline (requires `publish_mask:=true`)                              | `false`                        | —              |

> **Note:** `weight_file` and `weights_path` can only be changed when the node is in the `unconfigured` state (after `deactivate` + `cleanup`).

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Topics

### Publications

| Topic                        | Type                              | Description                          |
| ---------------------------- | --------------------------------- | ------------------------------------ |
| `<node>/object_boxes`        | `vision_msgs/Detection2DArray`    | Bounding boxes per detected instance |
| `<node>/object_masks`        | `sobits_interfaces/DetectMaskArray` | Instance masks (when `publish_mask:=true`) |
| `<node>/detected_image`      | `sensor_msgs/Image`               | Annotated visualization image        |

### Subscriptions

| Topic               | Type                    | Description          |
| ------------------- | ----------------------- | -------------------- |
| `<image_topic_name>` | `sensor_msgs/Image`    | Input camera image   |

> `<node>` defaults to `sam3_node`. Override with the `node_name` launch argument.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Demo
| Object Detection | Multi-class | Instance Segmentation |
|:---:|:---:|:---:|
| ![](docs/sam3_object_raw.png) | ![](docs/sam3_multiclass_raw.png) | ![](docs/sam3_instant_raw.png) |
| ![](docs/sam3_object_result.png) | ![](docs/sam3_multiclass_result.png) | ![](docs/sam3_instant_result.png) |

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## References
* [SAM 3: Segment Anything with Concepts](https://github.com/facebookresearch/sam3)
* [Ultralytics Documentation](https://docs.ultralytics.com/models/sam-3/)

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
