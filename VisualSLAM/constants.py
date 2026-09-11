import sys
import os
import json

VSLAM_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_CONFIG_PATH = os.path.join(VSLAM_DIR, "config", "gui_cfg.json")

with open(GUI_CONFIG_PATH, 'r') as f:
    GUI_CONFIG = json.load(f)


LAYERS_CONFIG = GUI_CONFIG.get('layers', {})

WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 750

LABEL_PAUSE = "Pause"
LABEL_LAYERS_SETTINGS = "Layers Settings"