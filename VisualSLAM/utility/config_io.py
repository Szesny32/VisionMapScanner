import json
import os

def load_config(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def save_config(filepath, config):
    tmp = filepath + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(config, f, indent=4)
    os.replace(tmp, filepath)

def apply_sources(config, layer):
    for item in config.get("layers", []):
        if item.get("name") == layer.name:
            item["sources"] = dict(layer.source_bindings)
            return True
    return False

def update_layer_sources(filepath, layer):
    config = load_config(filepath)
    if apply_sources(config, layer):
        save_config(filepath, config)