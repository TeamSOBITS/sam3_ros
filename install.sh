#!/bin/bash
set -e

ROS_DISTRO=${ROS_DISTRO:-jazzy}

clone_if_missing() {
  local repo="$1"
  local branch="$2"
  if [ ! -d "$repo" ]; then
    git clone -b "$branch" "https://github.com/TeamSOBITS/${repo}.git"
  fi
}

echo "╔══╣ Install: SAM3 ROS (STARTING) ╠══╗"

cd ..
clone_if_missing sobits_interfaces "${ROS_DISTRO}-devel"
clone_if_missing image_to_position "${ROS_DISTRO}-devel"

cd sobits_interfaces && bash install.sh && cd ..
cd image_to_position && bash install.sh && cd ..

python3 -m pip install --break-system-packages torch
python3 -m pip install --break-system-packages ultralytics "numpy>=1.26,<2"
python3 -m pip install --break-system-packages timm
python3 -m pip install --break-system-packages "git+https://github.com/ultralytics/CLIP.git"

sudo apt-get update
sudo apt-get install -y "ros-${ROS_DISTRO}-vision-msgs"

echo "╚══╣ Install: SAM3 ROS (FINISHED) ╠══╝"
