#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VSLAM_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$VSLAM_DIR"
./venv/bin/python -m pytest -q tests/test_depth_benchmark.py
./venv/bin/python scripts/benchmark_stereo_depth.py "$@"
