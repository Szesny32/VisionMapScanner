import os

from layer.pipeline import LayerGraph
from utility.load_layers_from_json import load_layers_from_json

GUI_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "gui_cfg.json")


def test_loads_all_layers_from_config():
    layers = load_layers_from_json(GUI_CONFIG_PATH)
    names = {l.name for l in layers}

    assert len(layers) == 7
    assert names == {
        "Left Camera",
        "Right Camera",
        "Stereo & Depth",
        "GT Depth (Unity)",
        "Keypoint Matching",
        "3D Point Cloud View",
        "2D Occupancy Grid",
    }


def test_octree_defaults_to_algorithm_depth():
    layers = load_layers_from_json(GUI_CONFIG_PATH)
    graph = LayerGraph(layers)

    octree = next(l for l in layers if l.name == "3D Point Cloud View")
    candidates = {out for _, out in graph.get_candidates("depth_map")}

    assert candidates == {"depth_map", "depth_map_gt"}
    graph.resolve()
    assert octree.resolved_inputs["depth_map"] == "depth_map"


def test_gt_depth_is_a_valid_alternative_source():
    layers = load_layers_from_json(GUI_CONFIG_PATH)
    graph = LayerGraph(layers)
    hexed = next(l for l in layers if l.name == "3D Point Cloud View")

    hexed.source_bindings["depth_map"] = "depth_map_gt"
    graph.resolve()

    assert hexed.resolved_inputs["depth_map"] == "depth_map_gt"