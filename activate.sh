#!/bin/bash
ROOT_DIR="$(git rev-parse --show-toplevel)"
VISUAL_SLAM_DIR="$ROOT_DIR/VisualSLAM"
ROS2_DIR="$VISUAL_SLAM_DIR/ros2"
SCRIPTS_DIR="$VISUAL_SLAM_DIR/scripts"

chmod +x "$ROS2_DIR/run_ros_tcp_endpoint.sh"
chmod +x "$ROS2_DIR/run_stereo_processor_node.sh"
chmod +x "$SCRIPTS_DIR/run_stereo_viewer.sh"
