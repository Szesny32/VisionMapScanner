import os

from utility.load_layers_from_json import load_layers_from_json

VSLAM_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_CONFIG_PATH = os.path.join(VSLAM_DIR, "config", "gui_cfg.json")

LAYERS = load_layers_from_json(GUI_CONFIG_PATH)

WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 750
PREVIEW_GRID_COLUMNS = 3

DEPTH_FIXTURE_PATH = os.path.join(VSLAM_DIR, "tests", "fixtures", "unity_startup")
DEPTH_BENCHMARK_MANIFEST_PATH = os.path.join(
    VSLAM_DIR, "tests", "fixtures", "unity_stereo_benchmark.json"
)
