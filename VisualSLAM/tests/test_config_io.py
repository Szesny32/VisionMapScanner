import json

from utility.config_io import load_config, save_config, apply_sources, update_layer_sources


CONFIG = {
    "layers": [
        {
            "type": "StereoLayer",
            "name": "Stereo & Depth",
            "enabled": True,
            "outputs": ["depth_map"],
            "params": {"max_depth": 10.0},
        },
        {
            "type": "OctreeLayer",
            "name": "3D Point Cloud View",
            "enabled": True,
            "sources": {"depth_map": "depth_map"},
            "params": {},
        },
    ]
}


def test_load_config(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(CONFIG))

    assert load_config(str(path)) == CONFIG


def test_save_config_round_trip(tmp_path):
    path = tmp_path / "cfg.json"
    save_config(str(path), CONFIG)

    assert json.loads(path.read_text()) == CONFIG


class FakeLayer:
    def __init__(self):
        self.name = "3D Point Cloud View"
        self.source_bindings = {"depth_map": "depth_map_gt"}


def test_apply_sources_updates_matching_layer(tmp_path):
    path = tmp_path / "cfg.json"
    save_config(str(path), CONFIG)

    config = load_config(str(path))
    updated = apply_sources(config, FakeLayer())

    assert updated is True
    assert config["layers"][1]["sources"] == {"depth_map": "depth_map_gt"}
    assert config["layers"][0] == CONFIG["layers"][0]


def test_update_layer_sources_persists(tmp_path):
    path = tmp_path / "cfg.json"
    save_config(str(path), CONFIG)

    update_layer_sources(str(path), FakeLayer())

    config = load_config(str(path))
    assert config["layers"][1]["sources"] == {"depth_map": "depth_map_gt"}
    assert not path.with_suffix(".tmp").exists()


def test_apply_sources_no_match_returns_false(tmp_path):
    class Unknown:
        def __init__(self):
            self.name = "absent"
            self.source_bindings = {}

    path = tmp_path / "cfg.json"
    save_config(str(path), CONFIG)

    assert apply_sources(load_config(str(path)), Unknown()) is False