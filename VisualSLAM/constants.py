import os

from utility.load_layers_from_json import load_layers_from_json

VSLAM_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_CONFIG_PATH = os.path.join(VSLAM_DIR, "config", "gui_cfg.json")

LAYERS = load_layers_from_json(GUI_CONFIG_PATH)

WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 750

LABEL_PAUSE = "Pause"
LABEL_LAYERS_SETTINGS = "Layers Settings"