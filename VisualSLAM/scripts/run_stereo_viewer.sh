#!/bin/bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash

ROOT_DIR="$(git rev-parse --show-toplevel)"
STEREO_DIR="$ROOT_DIR/VisualSLAM/stereo"

python3 "$STEREO_DIR/stereo_viewer.py"