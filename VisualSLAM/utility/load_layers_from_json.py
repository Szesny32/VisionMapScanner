import json
from layer.registry import LAYER_REGISTRY

def load_layers_from_json(filepath):
    with open(filepath, 'r') as f:
        config = json.load(f)

    layers = []
    for item in config.get("layers", []):
        layer_type = item.get("type")
        if layer_type not in LAYER_REGISTRY:
            continue

        cls = LAYER_REGISTRY[layer_type]
        layer = cls(*item.get("args", []))

        layer.name = item.get("name", layer.name)
        layer.enabled = item.get("enabled", layer.enabled)
        layer.grid_span = item.get("grid_span", layer.grid_span)
        if "inputs" in item:
            layer.inputs = list(item["inputs"])
        if "outputs" in item:
            layer.outputs = list(item["outputs"])
        if "provides" in item:
            layer.provides = dict(item["provides"])
        layer.source_bindings = dict(item.get("sources", {}))

        params = item.get("params", {})
        for k, v in params.items():
            if hasattr(layer, k):
                setattr(layer, k, v)

        if hasattr(layer, "rebuild_matchers"):
            layer.rebuild_matchers()

        layers.append(layer)

    return layers