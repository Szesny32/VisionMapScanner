import json
from layer.camera_layer import CameraLayer
from layer.stereo_layer import StereoLayer
from layer.keypoint_layer import KeypointLayer

def load_layers_from_json(filepath):
    with open(filepath, 'r') as f:
        config = json.load(f)
    
    layer_classes = {
        "CameraLayer": CameraLayer,
        "StereoLayer": StereoLayer,
        "KeypointLayer": KeypointLayer
    }
    
    layers = []
    for item in config.get("layers", []):
        layer_type = item.get("type")
        enabled = item.get("enabled", True)
        grid_span = item.get("grid_span", 1)
        inputs = item.get("inputs", [])
        params = item.get("params", {})
        
        if layer_type in layer_classes:
            cls = layer_classes[layer_type]
            
            if layer_type == "CameraLayer":
                layer = cls(item.get("name"), params.get("source_key", "left"))
            else:
                layer = cls()
                
            layer.enabled = enabled
            layer.grid_span = grid_span
            layer.inputs = inputs
            
            for k, v in params.items():
                if hasattr(layer, k):
                    setattr(layer, k, v)
                    
            layers.append(layer)
            
    return layers