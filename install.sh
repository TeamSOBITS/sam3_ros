echo "╔══╣ Install: SAM3 ROS (STARTING) ╠══╗"

cd ..
git clone -b ${ROS_DISTRO}-devel https://github.com/TeamSOBITS/sobits_interfaces.git
git clone -b ${ROS_DISTRO}-devel https://github.com/TeamSOBITS/image_to_position.git

cd sobits_interfaces/ && bash install.sh && cd ..
cd image_to_position/ && bash install.sh && cd ..

pip3 install torch --break-system-packages
pip3 install ultralytics "numpy<2" --break-system-packages
pip install timm --break-system-packages
pip install "git+https://github.com/ultralytics/CLIP.git" --break-system-packages 

sudo apt install ros-$ROS_DISTRO-vision-msgs


echo "╚══╣ Install: SAM3 ROS (FINISHED) ╠══╝"
