import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QSlider
from PySide6.QtCore import Qt
from layer.base_layer import BaseLayer, depth_to_visual

class GTDepthLayer(BaseLayer):
    def __init__(self):
        super().__init__("GT Depth (Unity)")
        self.outputs = ["depth_map_gt"]
        self.provides = {"depth_map": "depth_map_gt"}
        self.topic = "/stereo/camera_depth"
        self.min_depth = 0.1
        self.max_depth = 10.0
        self.num_disp_multiplier = 8

    def _build_custom_controls(self, layout):
        lbl_min = QLabel(f"Min Depth (m): {self.min_depth:.2f}")
        slider_min = QSlider(Qt.Horizontal)
        slider_min.setRange(1, 50)
        slider_min.setValue(int(self.min_depth * 100))

        def on_min_change(val):
            self.min_depth = val / 100.0
            lbl_min.setText(f"Min Depth (m): {self.min_depth:.2f}")

        slider_min.valueChanged.connect(on_min_change)

        lbl_max = QLabel(f"Max Depth (m): {self.max_depth:.1f}")
        slider_max = QSlider(Qt.Horizontal)
        slider_max.setRange(1, 30)
        slider_max.setValue(int(self.max_depth))

        def on_max_change(val):
            self.max_depth = float(val)
            lbl_max.setText(f"Max Depth (m): {self.max_depth:.1f}")

        slider_max.valueChanged.connect(on_max_change)

        layout.addWidget(lbl_min)
        layout.addWidget(slider_min)
        layout.addWidget(lbl_max)
        layout.addWidget(slider_max)

    def process(self, data):
        depth = data.get("depth_map_gt", None)
        f = data.get("f", None)
        b = data.get("baseline", None)

        if depth is None:
            self.context["gt_depth_visual"] = None
            data["depth_map_gt"] = None
            return

        depth_proc = depth.copy()
        h, w = depth_proc.shape

        # 1. Pobranie parametru num_disparities ze StereoLayer (domyślnie 128 px)
        num_disp = 16 * data.get("num_disp_multiplier", self.num_disp_multiplier)

        # 2. Siatka współrzędnych X
        x_grid = np.tile(np.arange(w), (h, 1))

        # 3. Maska 1: Sztywny margines SGBM (lewa krawędź nieobliczalna przez algorytm)
        invalid_mask = x_grid < num_disp

        # 4. Maska 2: Fizyczny brak pokrycia polami widzenia (paralaksa)
        if f is not None and b is not None:
            with np.errstate(divide='ignore', invalid='ignore'):
                disparity_gt = np.where(depth_proc > 0, (f * b) / depth_proc, 0)
            invalid_mask |= (x_grid < disparity_gt)

        # Wyzerowanie pikseli poza zakresem wspólnym
        depth_proc[invalid_mask] = 0.0

        # 5. Przycięcie wartości głębi do [min_depth, max_depth]
        # 5. Przycięcie wartości głębi do [min_depth, max_depth]
        valid_mask = depth_proc > 0
        
        # Zabezpieczenie przed pustą tablicą (gdy brak poprawnych pikseli)
        if np.any(valid_mask):
            gt_min = np.min(depth_proc[valid_mask])
            gt_max = np.max(depth_proc[valid_mask])
        else:
            gt_min, gt_max = 0.0, 0.0
            
        print(f"[GT] f={f}; b={b}; min={gt_min:.2f}; max={gt_max:.2f}")
        
        depth_proc[valid_mask] = np.clip(depth_proc[valid_mask], self.min_depth, self.max_depth)

        data["depth_map_gt"] = depth_proc

        # 6. Wizualizacja
        depth_visual = depth_to_visual(depth_proc, self.min_depth, self.max_depth)
        self.context["gt_depth_visual"] = cv2.cvtColor(depth_visual, cv2.COLOR_GRAY2BGR)

    def draw(self, data):
        return self.context.get("gt_depth_visual", None)