# Installation

## 1.ROS-TCP-Endpoint
```
cd ~/ros2_ws/src
git clone -b main-ros2 https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git
cd ~/ros2_ws
colcon build --packages-select ros_tcp_endpoint
source install/setup.bash
```
## 2. Activate scripts
```
chmod +x activate.sh
./activate.sh
```

# Run

## 1. [Terminal-1]
```
./VisualSLAM/ros2/run_ros_tcp_endpoint.sh
```

## 2. Open & Run Unity project
- [[StereoVision Scene]]


## 3. [Terminal-2]
```
./VisualSLAM/ros2/run_stereo_processor_node.sh
```
