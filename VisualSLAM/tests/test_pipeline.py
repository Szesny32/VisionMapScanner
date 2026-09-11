import pytest

from layer.pipeline import LayerGraph


class StubLayer:
    def __init__(self, name, inputs=(), outputs=(), provides=None, sources=None, enabled=True):
        self.name = name
        self.enabled = enabled
        self.inputs = list(inputs)
        self.outputs = list(outputs)
        self.provides = dict(provides) if provides is not None else {o: o for o in self.outputs}
        self.source_bindings = dict(sources or {})
        self.resolved_inputs = {}
        self.skip_if_present = False
        self.processed = 0
        self.read_values = {}

    def _input_key(self, semantic_key):
        if semantic_key in self.resolved_inputs:
            return self.resolved_inputs[semantic_key]
        if semantic_key in self.source_bindings:
            return self.source_bindings[semantic_key]
        return semantic_key

    def process(self, data):
        self.processed += 1
        for k in self.inputs:
            self.read_values[k] = data.get(self._input_key(k))
        for out in self.outputs:
            data[out] = f"{self.name}:{out}"

    def draw(self, data):
        return None


def test_providers_run_before_consumers():
    stereo = StubLayer("stereo", inputs=["left", "right"], outputs=["depth_map"])
    depth_gt = StubLayer("gt", outputs=["depth_map_gt"], provides={"depth_map": "depth_map_gt"})
    octree = StubLayer("octree", inputs=["depth_map"], outputs=["points"])
    graph = LayerGraph([octree, stereo, depth_gt])

    order = graph.resolve()

    assert order.index(stereo) < order.index(octree)
    assert order.index(depth_gt) < order.index(octree)
    assert octree.resolved_inputs["depth_map"] == "depth_map"


def test_source_binding_redirects_input():
    stereo = StubLayer("stereo", inputs=["left", "right"], outputs=["depth_map"])
    depth_gt = StubLayer("gt", outputs=["depth_map_gt"], provides={"depth_map": "depth_map_gt"})
    octree = StubLayer(
        "octree",
        inputs=["depth_map"],
        outputs=["points"],
        sources={"depth_map": "depth_map_gt"},
    )
    graph = LayerGraph([stereo, depth_gt, octree])

    data = {"frame_id": 1}
    graph.run(data)

    assert octree.resolved_inputs["depth_map"] == "depth_map_gt"
    assert octree.read_values["depth_map"] == "gt:depth_map_gt"
    assert data["depth_map_gt"] == "gt:depth_map_gt"


def test_disabled_provider_falls_back_to_enabled():
    stereo = StubLayer("stereo", inputs=["left", "right"], outputs=["depth_map"], enabled=False)
    depth_gt = StubLayer("gt", outputs=["depth_map_gt"], provides={"depth_map": "depth_map_gt"})
    octree = StubLayer("octree", inputs=["depth_map"], outputs=["points"])
    graph = LayerGraph([stereo, depth_gt, octree])

    graph.resolve()

    assert octree.resolved_inputs["depth_map"] == "depth_map_gt"


def test_unknown_input_resolves_to_itself():
    layer = StubLayer("l", inputs=["left"], outputs=[])
    graph = LayerGraph([layer])
    graph.resolve()

    assert layer.resolved_inputs["left"] == "left"


def test_cycle_detection_raises():
    a = StubLayer("a", inputs=["b"], outputs=["a"], provides={"a": "a"})
    b = StubLayer("b", inputs=["a"], outputs=["b"], provides={"b": "b"})
    graph = LayerGraph([a, b])

    with pytest.raises(RuntimeError, match="cycle"):
        graph.resolve()


def test_disabled_layers_are_not_processed():
    layer = StubLayer("l", inputs=[], outputs=["x"], enabled=False)
    graph = LayerGraph([layer])

    results = graph.run({"frame_id": 1})

    assert layer.processed == 0
    assert "l" not in results


def test_skip_if_present_skips_processing():
    layer = StubLayer("l", inputs=[], outputs=["x"])
    layer.skip_if_present = True
    graph = LayerGraph([layer])

    graph.run({"frame_id": 1, "x": "already"})

    assert layer.processed == 0

    graph.run({"frame_id": 2})

    assert layer.processed == 1


def test_run_returns_non_none_draws_only():
    class DrawLayer(StubLayer):
        def __init__(self, name, value):
            super().__init__(name, inputs=[], outputs=[name])
            self.value = value

        def draw(self, data):
            return self.value

    none_layer = DrawLayer("none", None)
    img_layer = DrawLayer("img", "image")
    graph = LayerGraph([none_layer, img_layer])

    results = graph.run({"frame_id": 1})

    assert results == {"img": "image"}
    assert none_layer in graph.resolve()