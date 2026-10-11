import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QComboBox, QLabel
from PySide6.QtCore import Qt


def depth_to_visual(depth, min_depth, max_depth):
    if depth is None or max_depth <= min_depth:
        shape = (0, 0) if depth is None else np.asarray(depth).shape[:2]
        return np.zeros(shape, dtype=np.uint8)
    d = np.asarray(depth, dtype=np.float32)
    invalid = (d <= 0.0) | (d > max_depth)
    d_clipped = np.clip(d, min_depth, max_depth)
    visual = 255.0 * (1.0 - (d_clipped - min_depth) / (max_depth - min_depth))
    visual[invalid] = 0.0
    return np.clip(visual, 0.0, 255.0).astype(np.uint8)


class BaseLayer:
    def __init__(self, name=None, enabled=True, grid_span=1, inputs=None, max_cache_frames=5):
        self.name = name if name is not None else self.__class__.__name__
        self.enabled = enabled
        self.grid_span = grid_span
        self.inputs = list(inputs) if inputs else []
        self.outputs = []
        self.provides = {}
        self.source_bindings = {}
        self.resolved_inputs = {}
        self.skip_if_present = False
        self.settings_saver = None
        self.config_changed_callback = None
        self.context = {}
        self.max_cache_frames = max_cache_frames
        self._cache = {}

    def _input_key(self, semantic_key):
        if semantic_key in self.resolved_inputs:
            return self.resolved_inputs[semantic_key]
        if semantic_key in self.source_bindings:
            return self.source_bindings[semantic_key]
        return semantic_key

    def create_control_widget(self, on_toggle_callback=None, graph=None) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 5)

        chk = QCheckBox(self.name)
        chk.setChecked(self.enabled)
        chk.setStyleSheet("font-weight: bold; color: #fff;")

        def _on_state_changed(state):
            self.enabled = (state == Qt.Checked.value or state == 2)
            if on_toggle_callback:
                on_toggle_callback()
            self.notify_config_changed()

        chk.stateChanged.connect(_on_state_changed)
        layout.addWidget(chk)

        self._build_source_selectors(layout, graph)
        self._build_custom_controls(layout)

        return widget

    def _build_source_selectors(self, layout: QVBoxLayout, graph):
        if graph is None:
            return

        for inp in self.inputs:
            candidates = graph.get_candidates(inp)
            if len(candidates) <= 1:
                continue

            current_out = self._input_key(inp)

            row = QHBoxLayout()
            row.addWidget(QLabel(inp))

            combo = QComboBox()
            selected_index = 0
            for i, (provider_name, out_key) in enumerate(candidates):
                combo.addItem(f"{provider_name} ({out_key})", out_key)
                if out_key == current_out:
                    selected_index = i
            combo.setCurrentIndex(selected_index)

            def _on_source_change(index, k=inp, source_combo=combo):
                out_key = source_combo.itemData(index)
                if out_key is None:
                    return
                self.source_bindings[k] = out_key
                if self.settings_saver:
                    self.settings_saver(self)
                self.notify_config_changed()

            combo.currentIndexChanged.connect(_on_source_change)
            row.addWidget(combo, 1)
            layout.addLayout(row)

    def _build_custom_controls(self, layout: QVBoxLayout):
        pass

    def notify_config_changed(self):
        if self.config_changed_callback is not None:
            self.config_changed_callback()

    def _check_cache(self, frame_id, output_key):
        if frame_id is not None and frame_id in self._cache:
            if output_key in self._cache[frame_id]:
                self.context[output_key] = self._cache[frame_id][output_key]
                return True
        return False

    def _save_to_cache(self, frame_id, output_key, value):
        if frame_id is None:
            return
        if frame_id not in self._cache:
            self._cache[frame_id] = {}
        self._cache[frame_id][output_key] = value

        if len(self._cache) > self.max_cache_frames:
            oldest_key = min(self._cache.keys())
            del self._cache[oldest_key]

    def _get_from_cache(self, frame_id, output_key):
        if frame_id is not None and frame_id in self._cache:
            return self._cache[frame_id].get(output_key)
        return None

    def process(self, data):
        raise NotImplementedError

    def draw(self, data):
        raise NotImplementedError
