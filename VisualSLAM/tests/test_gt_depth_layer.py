import numpy as np

from layer.gt_depth_layer import GTDepthLayer


def _bgr_visual(layer, img):
    layer.process({"depth_map_gt": img})
    return layer.draw({})


def test_none_input_returns_no_visual():
    layer = GTDepthLayer()
    data = {"depth_map_gt": None}

    layer.process(data)
    assert data["depth_map_gt"] is None
    assert layer.draw({}) is None


def test_visual_shape_matches_input():
    layer = GTDepthLayer()
    depth = np.full((64, 48), 5.0, dtype=np.float32)

    visual = _bgr_visual(layer, depth)

    assert visual.dtype == np.uint8
    assert visual.shape == (64, 48, 3)


def test_visual_mapping_formula():
    layer = GTDepthLayer()
    v = np.array([[[0.1], [5.05], [10.0]]], dtype=np.float32)

    visual = _bgr_visual(layer, v)

    expected = (255.0 * (1.0 - (np.array([0.0, 0.5, 1.0])))).astype(np.uint8)
    np.testing.assert_array_equal(visual[0, :, 0], expected)
    np.testing.assert_array_equal(visual[0, :, 1], expected)
    np.testing.assert_array_equal(visual[0, :, 2], expected)


def test_clipping_beyond_range():
    layer = GTDepthLayer()
    depth = np.array([-1.0, 20.0], dtype=np.float32).reshape(1, 2)

    visual = _bgr_visual(layer, depth)

    assert visual[0, 0, 0] == 0
    assert visual[0, 1, 0] == 0


def test_custom_min_max_are_config_driven():
    layer = GTDepthLayer()
    layer.min_depth = 0.0
    layer.max_depth = 20.0
    depth = np.array([[10.0]], dtype=np.float32)

    visual = _bgr_visual(layer, depth)

    assert visual[0, 0, 0] == 127


def test_does_not_mutate_input_depth():
    layer = GTDepthLayer()
    depth = np.full((4, 4), 3.0, dtype=np.float32)
    original = depth.copy()

    layer.process({"depth_map_gt": depth})

    np.testing.assert_array_equal(depth, original)
