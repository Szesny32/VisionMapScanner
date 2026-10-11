import json
from types import SimpleNamespace

import numpy as np

from layer.depth_config import StereoDepthConfig
from layer.depth_provider import DepthProvider
from layer.gt_depth_layer import GTDepthLayer
from layer.pipeline import LayerGraph
from layer.stereo_layer import StereoLayer
from ros.bridge_controller import ROS2BridgeController
from ros.ros_thread import ROSThread
from utility.load_layers_from_json import load_layers_from_json
from utility.depth_selection import gt_depth_stream_requested
from constants import GUI_CONFIG_PATH


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class FakeClock:
    def __init__(self):
        self.nanoseconds = 0

    def now(self):
        return self


class FakeLogger:
    def __init__(self):
        self.errors = []
        self.infos = []

    def error(self, message):
        self.errors.append(message)

    def info(self, message):
        self.infos.append(message)


class FakeNode:
    def __init__(self):
        self.publisher = FakePublisher()
        self.clock = FakeClock()
        self.logger = FakeLogger()

    def create_publisher(self, *_args):
        return self.publisher

    def create_subscription(self, *_args):
        return object()

    def get_clock(self):
        return self.clock

    def get_logger(self):
        return self.logger


class CapturingGraph:
    def __init__(self):
        self.frames = []

    def run(self, frame):
        self.frames.append(frame)
        return frame


def test_depth_provider_normalizes_to_float32_h_w_meters():
    source = np.array([[[1.25], [2.5]]], dtype=np.float64)

    result = DepthProvider.normalize_depth_map(source)

    assert result.dtype == np.float32
    assert result.shape == (1, 2)
    np.testing.assert_allclose(result, [[1.25, 2.5]])


def test_depth_provider_rejects_missing_empty_and_non_image_data():
    assert DepthProvider.normalize_depth_map(None) is None
    assert DepthProvider.normalize_depth_map(np.empty((0, 5))) is None
    assert DepthProvider.normalize_depth_map(np.zeros((2, 2, 3))) is None


def test_both_depth_layers_return_none_for_missing_or_empty_inputs():
    stereo = StereoLayer()
    stereo_data = {"left": None, "right": None, "f": None, "baseline": None}
    stereo.process(stereo_data)
    assert stereo_data["depth_map"] is None
    assert stereo.draw({}) is None

    gt_data = {"depth_map_gt": np.empty((0, 3), dtype=np.float32)}
    GTDepthLayer().process(gt_data)
    assert gt_data["depth_map_gt"] is None

    mismatched_data = {
        "depth_map_gt": np.ones((3, 3), dtype=np.float32),
        "left": np.zeros((2, 3, 3), dtype=np.uint8),
    }
    GTDepthLayer().process(mismatched_data)
    assert mismatched_data["depth_map_gt"] is None


def test_pipeline_keeps_per_consumer_depth_source_selection():
    layers = load_layers_from_json(GUI_CONFIG_PATH)
    octree = next(layer for layer in layers if layer.name == "3D Point Cloud View")
    occupancy = next(layer for layer in layers if layer.name == "2D Occupancy Grid")
    octree.source_bindings["depth_map"] = "depth_map_gt"

    LayerGraph(layers).resolve()

    assert octree.resolved_inputs["depth_map"] == "depth_map_gt"
    assert occupancy.resolved_inputs["depth_map"] == "depth_map"


def test_enabled_gt_preview_requests_unity_depth_even_when_consumers_use_opencv():
    layers = load_layers_from_json(GUI_CONFIG_PATH)
    gt_layer = next(layer for layer in layers if isinstance(layer, GTDepthLayer))
    octree = next(layer for layer in layers if layer.name == "3D Point Cloud View")
    occupancy = next(layer for layer in layers if layer.name == "2D Occupancy Grid")
    gt_layer.enabled = True
    octree.source_bindings["depth_map"] = "depth_map"
    occupancy.source_bindings["depth_map"] = "depth_map"

    assert gt_depth_stream_requested(layers) is True

    gt_layer.enabled = False
    assert gt_depth_stream_requested(layers) is False


def test_stereo_and_gt_return_same_matrix_contract():
    config = StereoDepthConfig(min_disp=0, num_disp_multiplier=8)
    stereo = StereoLayer(depth_config=config)
    width = 160
    filtered_disparity = np.full((2, width), 32, dtype=np.int16)
    filtered_disparity[0, 150] = 0
    stereo.stereo_matcher = SimpleNamespace(
        compute=lambda _left, _right: filtered_disparity
    )
    stereo.right_matcher = SimpleNamespace(
        compute=lambda _right, _left: np.full((2, width), -32, dtype=np.int16)
    )
    stereo.wls_filter = SimpleNamespace(
        filter=lambda disp, _left, disparity_map_right: disp
    )
    stereo_data = {
        "left": np.zeros((2, width, 3), dtype=np.uint8),
        "right": np.zeros((2, width, 3), dtype=np.uint8),
        "f": 2.0,
        "baseline": 1.0,
        "_collect_depth_diagnostics": True,
    }
    stereo.process(stereo_data)

    gt_depth_source = np.full((2, width, 1), 1.0, dtype=np.float64)
    gt_depth_source[0, 150, 0] = 0.0
    gt_data = {
        "depth_map_gt": gt_depth_source,
        "f": 2.0,
        "baseline": 1.0,
    }
    gt_layer = GTDepthLayer(depth_config=config)
    gt_layer.process(gt_data)

    stereo_depth = stereo_data["depth_map"]
    gt_depth = gt_data["depth_map_gt"]
    assert stereo_depth.dtype == gt_depth.dtype == np.float32
    assert stereo_depth.shape == gt_depth.shape == (2, width)
    np.testing.assert_array_equal(stereo_depth, gt_depth)
    np.testing.assert_array_equal(stereo.draw({}), gt_layer.draw({}))
    assert stereo_depth[0, 150] == 0.0
    assert np.all(stereo_depth[:, :128] == 0.0)
    assert stereo_depth[1, 129] == 1.0
    assert stereo_data["_depth_diagnostics"]["opencv"]["masked_pixels"] == 256
    disparity_stats = stereo_data["_depth_diagnostics"]["opencv"]["filtered_disparity"]
    assert disparity_stats["p50_px"] == 2.0
    assert sum(stereo_data["_depth_diagnostics"]["opencv"]["range_histogram"]["counts"]) > 0


def test_shared_depth_postprocessing_preserves_invalids_and_caps_valid_values():
    raw = np.array([[0.0, 0.05, 2.0, 12.0, np.nan, 4.0]], dtype=np.float32)
    support = np.array([[True, True, True, True, True, False]])

    result = DepthProvider.postprocess_depth_map(raw, 0.1, 10.0, support)

    assert result.dtype == np.float32
    assert result.shape == (1, 6)
    np.testing.assert_allclose(result, [[0.0, 0.1, 2.0, 10.0, 0.0, 0.0]])


def test_depth_statistics_report_range_percentiles_and_invalid_pixel_counts():
    stats = DepthProvider.depth_statistics(
        np.array([[0.0, 1.0, 2.0, 3.0, np.nan]], dtype=np.float32)
    )

    assert stats["zero"] == 1
    assert stats["nonfinite"] == 1
    assert stats["valid"] == 3
    assert stats["min"] == 1.0
    assert stats["max"] == 3.0
    assert stats["p50"] == 2.0


def test_bridge_diagnostic_format_includes_synchronized_depth_statistics():
    message = ROS2BridgeController._format_depth_diagnostics({
        "stamp": 12.5,
        "providers": {
            "opencv": {
                "before_mask": {
                    "min": 0.2, "max": 8.0, "p50": 2.0, "p90": 5.0, "p99": 7.0,
                    "zero": 20, "nonfinite": 1, "valid": 100,
                },
                "after_mask": {
                    "min": 0.2, "max": 8.0, "p50": 2.0, "p90": 5.0, "p99": 7.0,
                    "zero": 30, "nonfinite": 0, "valid": 90,
                },
                "masked_pixels": 10,
                "filtered_disparity": {
                    "valid": 100, "invalid": 10, "p01_px": 1.0,
                    "p50_px": 2.0, "p90_px": 4.0, "p99_px": 5.0,
                },
                "range_histogram": {
                    "counts": [90, 10], "below_min": 2, "above_max": 3,
                },
            },
        },
        "camera_info": {"focal_length": 620.0, "baseline": 0.1},
        "depth_config": {"min_depth": 0.1, "max_depth": 10.0},
    })

    assert "stereo_stamp=12.500000000" in message
    assert "p99=7.000" in message
    assert "zero=30 nonfinite=0 valid=90 masked=10" in message
    assert "disparity[valid=100 invalid=10 p01=1.00" in message
    assert "range_bins=[90, 10]" in message
    assert "f=620.00px baseline=0.1000m" in message


def test_depth_message_decoder_validates_shape_and_normalizes_millimeters():
    msg = SimpleNamespace(
        height=1,
        width=2,
        encoding="16UC1",
        data=np.array([1000, 2500], dtype=np.uint16).tobytes(),
    )
    result = ROS2BridgeController.image_message_to_depth(msg)

    assert result.dtype == np.float32
    np.testing.assert_allclose(result, [[1.0, 2.5]])
    malformed = SimpleNamespace(height=2, width=2, encoding="32FC1", data=b"bad")
    assert ROS2BridgeController.image_message_to_depth(malformed) is None


def test_config_loader_shares_one_runtime_stereo_configuration():
    layers = load_layers_from_json(GUI_CONFIG_PATH)
    providers = [layer for layer in layers if hasattr(layer, "depth_config")]

    assert len(providers) == 2
    assert providers[0].depth_config is providers[1].depth_config
    assert providers[0].depth_config.width == 1080
    assert providers[0].depth_config.baseline == 0.38


def test_runtime_configuration_is_sent_at_start_even_when_gt_is_inactive():
    layers = load_layers_from_json(GUI_CONFIG_PATH)
    thread = ROSThread(layers, LayerGraph(layers))

    thread.set_runtime_configuration(active=False)
    initial = thread.runtime_state()
    assert initial["revision"] == 1
    assert json.loads(initial["payload"])["gt_enabled"] is False

    thread.set_runtime_configuration(active=False)
    assert thread.runtime_state()["revision"] == 1

    thread.set_runtime_configuration(active=True)
    first = thread.runtime_state()
    assert first["revision"] == 2
    assert json.loads(first["payload"])["revision"] == 2
    assert json.loads(first["payload"])["gt_enabled"] is True

    thread.set_runtime_configuration(active=True)
    assert thread.runtime_state()["revision"] == 2

    thread.depth_config.max_depth = 12.0
    thread.set_runtime_configuration(active=True)
    assert thread.runtime_state()["revision"] == 3
    assert json.loads(thread.runtime_state()["payload"])["max_depth"] == 12.0

    thread.set_runtime_configuration(active=False)
    inactive = thread.runtime_state()
    assert inactive["revision"] == 4
    assert json.loads(inactive["payload"])["gt_enabled"] is False


def test_pipeline_exception_is_logged_and_next_frame_is_processed():
    class FailFirstGraph:
        def __init__(self):
            self.calls = 0

        def run(self, frame):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("synthetic GT layer failure")
            return {"frame_id": frame["frame_id"]}

    node = FakeNode()
    graph = FailFirstGraph()
    emitted = []
    controller = ROS2BridgeController(
        node, graph, emitted.append,
        lambda: {"active": False, "config": {"gt_enabled": False}},
        lambda: False,
    )
    image = np.zeros((2, 3, 3), dtype=np.uint8)

    for frame_id in (1, 2):
        controller._emit_stereo_frame(
            {"frame_id": frame_id, "stamp": float(frame_id), "left": image, "right": image},
            None,
            {"gt_enabled": False},
        )

    assert graph.calls == 2
    assert emitted == [{"frame_id": 2}]
    assert controller.processed_frame_count == 1
    assert controller.pipeline_error_count == 1
    assert "synthetic GT layer failure" in node.logger.errors[0]
    assert "Traceback" in node.logger.errors[0]


def test_deactivating_gt_publishes_a_disable_snapshot_to_unity():
    node = FakeNode()
    state = {
        "active": False,
        "revision": 4,
        "payload": json.dumps({"revision": 4, "gt_enabled": False}),
        "config": {"gt_enabled": False},
    }
    controller = ROS2BridgeController(
        node, CapturingGraph(), lambda _result: None,
        lambda: state, lambda: False,
    )

    controller.publish_pending_configuration()

    assert len(node.publisher.messages) == 1
    assert json.loads(node.publisher.messages[0].data) == {
        "revision": 4,
        "gt_enabled": False,
    }


def test_depth_config_rejects_invalid_camera_ranges_and_dimensions():
    assert StereoDepthConfig().validate()
    assert not StereoDepthConfig(min_depth=2.0, max_depth=1.0).validate()
    assert not StereoDepthConfig(width=0).validate()
    assert not StereoDepthConfig(p2_scale=17.0).validate()
    assert StereoDepthConfig(wls_lambda=100000.0, wls_sigma=7.0).validate()
    assert not StereoDepthConfig(wls_lambda=100001.0).validate()
    assert not StereoDepthConfig(wls_sigma=10.1).validate()


def test_bridge_only_processes_stereo_images_with_matching_timestamps():
    graph = CapturingGraph()
    controller = ROS2BridgeController(
        FakeNode(), graph, lambda _result: None,
        lambda: {"active": False, "config": {}}, lambda: False,
    )
    controller.left_image = np.zeros((2, 3, 3), dtype=np.uint8)
    controller.right_image = np.zeros((2, 3, 3), dtype=np.uint8)
    controller.left_stamp = 1.0
    controller.right_stamp = 1.01
    controller.try_process_synchronized_frame()
    assert graph.frames == []

    controller.left_image = np.zeros((2, 3, 3), dtype=np.uint8)
    controller.right_image = np.zeros((2, 3, 3), dtype=np.uint8)
    controller.left_stamp = 2.0
    controller.right_stamp = 2.0005
    controller.try_process_synchronized_frame()

    assert len(graph.frames) == 1
    frame = graph.frames[0]
    assert frame["camera_info"] == {
        "focal_length": 500.0,
        "baseline": 0.38,
        "width": 3,
        "height": 2,
        "depth_units": "m",
        "left": None,
        "right": None,
    }


def test_selected_gt_waits_for_depth_with_the_same_timestamp():
    graph = CapturingGraph()
    controller = ROS2BridgeController(
        FakeNode(), graph, lambda _result: None,
        lambda: {"active": True, "config": {}}, lambda: False,
    )
    controller.left_image = np.zeros((2, 3, 3), dtype=np.uint8)
    controller.right_image = np.zeros((2, 3, 3), dtype=np.uint8)
    controller.left_stamp = 3.0
    controller.right_stamp = 3.0
    controller.try_process_synchronized_frame()
    assert graph.frames == []

    controller.depth_image_callback(SimpleNamespace(
        height=2,
        width=3,
        encoding="32FC1",
        data=np.ones((2, 3), dtype=np.float32).tobytes(),
        header=SimpleNamespace(stamp=SimpleNamespace(sec=3, nanosec=0)),
    ))
    assert len(graph.frames) == 1
    np.testing.assert_array_equal(graph.frames[0]["depth_map_gt"], np.ones((2, 3)))
    assert graph.frames[0]["depth_stamp"] == 3.0


def test_missing_gt_frames_cannot_block_the_pipeline_indefinitely():
    graph = CapturingGraph()
    state = {"active": True, "config": {}}
    controller = ROS2BridgeController(
        FakeNode(), graph, lambda _result: None,
        lambda: state, lambda: False,
    )

    for frame_number in range(controller.MAX_PENDING_STEREO_FRAMES + 1):
        controller.left_image = np.zeros((2, 3, 3), dtype=np.uint8)
        controller.right_image = np.zeros((2, 3, 3), dtype=np.uint8)
        controller.left_stamp = float(frame_number)
        controller.right_stamp = float(frame_number)
        controller.try_process_synchronized_frame()

    assert len(graph.frames) == 1
    assert graph.frames[0]["depth_map_gt"] is None

    state["active"] = False
    controller.process_pending_stereo_frames()
    assert len(graph.frames) == controller.MAX_PENDING_STEREO_FRAMES + 1


def test_config_publisher_waits_for_ack_and_does_not_repeat_acknowledged_snapshot():
    node = FakeNode()
    controller = ROS2BridgeController(
        node, CapturingGraph(), lambda _result: None,
        lambda: {
            "active": True,
            "revision": 4,
            "payload": '{"revision":4}',
            "config": {},
        },
        lambda: False,
    )

    controller.publish_pending_configuration()
    assert [message.data for message in node.publisher.messages] == ['{"revision":4}']

    controller.configuration_ack_callback(SimpleNamespace(data='{"revision":4}'))
    controller.publish_pending_configuration()
    node.clock.nanoseconds = int(5e9)
    controller.publish_pending_configuration()
    assert len(node.publisher.messages) == 1
