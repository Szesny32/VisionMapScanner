from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox
from PySide6.QtCore import Qt

class BaseLayer:
    def __init__(self, name=None, enabled=True, grid_span=1, inputs=None):
        self.name = name if name is not None else self.__class__.__name__
        self.enabled = enabled
        self.grid_span = grid_span
        self.inputs = inputs or []
        self.context = {}
        
        self._cache = {}
        self._current_frame_id = None

    def create_control_widget(self, on_toggle_callback=None) -> QWidget:
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

        chk.stateChanged.connect(_on_state_changed)
        layout.addWidget(chk)

        # Wywołanie metody do nadpisania w klasach potomnych
        self._build_custom_controls(layout)

        return widget

    def _build_custom_controls(self, layout: QVBoxLayout):
        pass

    def _check_cache(self, frame_id, output_key):
        if frame_id is not None and frame_id in self._cache:
            if output_key in self._cache[frame_id]:
                self.context[output_key] = self._cache[frame_id][output_key]
                return True
        return False

    def _save_to_cache(self, frame_id, output_key, value):
        if frame_id is not None:
            if frame_id not in self._cache:
                self._cache[frame_id] = {}
            self._cache[frame_id][output_key] = value
            
            if len(self._cache) > 5:
                oldest_key = min(self._cache.keys())
                del self._cache[oldest_key]

    def process(self, data):
        raise NotImplementedError

    def draw(self, data):
        raise NotImplementedError