#!/usr/bin/env python3
"""Run the fixed Unity stereo/GT fixture and maintain its best-result manifest."""

import argparse
import hashlib
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VSLAM_DIR = os.path.dirname(SCRIPT_DIR)
if VSLAM_DIR not in sys.path:
    sys.path.insert(0, VSLAM_DIR)

from constants import DEPTH_BENCHMARK_MANIFEST_PATH, DEPTH_FIXTURE_PATH
from utility.depth_benchmark import run_fixture_benchmark, update_benchmark_manifest


OPENCV_CONFIG_FIELDS = (
    "baseline",
    "min_disp",
    "num_disp_multiplier",
    "block_size",
    "p2_scale",
    "wls_lambda",
    "wls_sigma",
)

SOURCE_FILES = (
    "layer/stereo_layer.py",
    "layer/depth_config.py",
    "layer/depth_provider.py",
    "layer/gt_depth_layer.py",
    "utility/depth_benchmark.py",
    "ros/bridge_controller.py",
    "scripts/run_ros_tcp_endpoint.sh",
    "config/gui_cfg.json",
    "../StereoVisionFrameProvider/Assets/Scripts/StereovisionCaptureROS2.cs",
    "../StereoVisionFrameProvider/Assets/Scripts/SystemUtility/ShellManager.cs",
)


def _source_revision():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=VSLAM_DIR, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _source_signature():
    signature = {}
    for relative_path in SOURCE_FILES:
        absolute_path = os.path.abspath(os.path.join(VSLAM_DIR, relative_path))
        try:
            with open(absolute_path, "rb") as source:
                signature[relative_path] = hashlib.sha256(source.read()).hexdigest()
        except OSError:
            signature[relative_path] = None
    return signature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=DEPTH_FIXTURE_PATH)
    parser.add_argument("--manifest", default=DEPTH_BENCHMARK_MANIFEST_PATH)
    parser.add_argument("--change-id", default="working-tree")
    parser.add_argument(
        "--change-description", default="Unlabeled OpenCV depth candidate"
    )
    parser.add_argument(
        "--use-captured-config",
        action="store_true",
        help="Use the OpenCV settings stored with the Unity frame instead of current Python UI settings.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.fixture):
        parser.error(
            "Unity startup fixture directory not found. Start the Unity scene once: %s"
            % args.fixture
        )

    try:
        config_overrides = None
        if not args.use_captured_config:
            config_path = os.path.join(VSLAM_DIR, "config", "gui_cfg.json")
            with open(config_path, encoding="utf-8") as source:
                ui_config = json.load(source)
            saved_stereo_config = ui_config.get("stereo_config", {})
            config_overrides = {
                key: saved_stereo_config[key]
                for key in OPENCV_CONFIG_FIELDS
                if key in saved_stereo_config
            }
        result = run_fixture_benchmark(args.fixture, config_overrides)
        accepted, manifest = update_benchmark_manifest(
            args.manifest,
            args.fixture,
            result,
            args.change_id,
            args.change_description,
            _source_revision(),
            _source_signature(),
        )
    except (OSError, TypeError, ValueError, KeyError) as error:
        parser.error(str(error))

    latest = manifest["last_attempt"] if accepted else None
    print(json.dumps({
        "status": latest["status"] if accepted else "rejected",
        "reason": latest["reason"] if accepted else (
            "Candidate must lower MAE without reducing OpenCV coverage; manifest unchanged."
        ),
        "metrics": result["metrics"],
        "frame_results": result.get("frames", []),
        "saved_artifacts": result.get("saved_artifacts", []),
        "best_metrics": manifest.get("best", {}).get("metrics"),
        "manifest": os.path.abspath(args.manifest),
    }, indent=2, sort_keys=True))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
