#!/bin/bash
ROOT_DIR="$(git rev-parse --show-toplevel)"
VISUAL_SLAM_DIR="$ROOT_DIR/VisualSLAM"
SCRIPTS_DIR="$VISUAL_SLAM_DIR/scripts"

chmod +x "$SCRIPTS_DIR/run_ros_tcp_endpoint.sh"
chmod +x "$SCRIPTS_DIR/run_stereo_processor_node.sh"
chmod +x "$SCRIPTS_DIR/run_stereo_viewer.sh"
