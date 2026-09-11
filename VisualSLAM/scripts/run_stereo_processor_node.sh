#!/bin/bash
ROOT_DIR="$(git rev-parse --show-toplevel)"
VSLAM_DIR="$ROOT_DIR/VisualSLAM"

source "$VSLAM_DIR/venv/bin/activate"

pip install --quiet -r "$VSLAM_DIR/requirements.txt"

export PYTHONPATH="$ROOT_DIR"


source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash

python3 "$VSLAM_DIR/main.py"