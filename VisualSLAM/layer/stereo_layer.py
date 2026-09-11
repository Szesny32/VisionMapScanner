import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QSlider
from PySide6.QtCore import Qt
from layer.base_layer import BaseLayer

class StereoLayer(BaseLayer):
    def __init__(self):
        super().__init__("Stereo & Depth")
        self.outputs = ["depth_map"]
        self.provides = {"depth_map": "depth_map"}
        self.min_disp = 0
        self.num_disp_multiplier = 8
        self.block_size = 5
        self.wls_lambda = 8000.0
        self.wls_sigma = 1.5
        self.max_depth = 10.0
        self.rebuild_matchers()

    def _build_custom_controls(self, layout):
        # Block Size
        lbl_bs = QLabel(f"Block Size: {self.block_size}")
        slider_bs = QSlider(Qt.Horizontal)
        slider_bs.setRange(1, 11)
        slider_bs.setValue((self.block_size - 1) // 2)

        def on_bs_change(val):
            self.block_size = 2 * val + 1
            lbl_bs.setText(f"Block Size: {self.block_size}")
            self.rebuild_matchers()

        slider_bs.valueChanged.connect(on_bs_change)

        # Num Disparities
        lbl_nd = QLabel(f"Num Disparities: {16 * self.num_disp_multiplier}")
        slider_nd = QSlider(Qt.Horizontal)
        slider_nd.setRange(1, 16)
        slider_nd.setValue(self.num_disp_multiplier)

        def on_nd_change(val):
            self.num_disp_multiplier = val
            lbl_nd.setText(f"Num Disparities: {16 * val}")
            self.rebuild_matchers()

        slider_nd.valueChanged.connect(on_nd_change)

        # WLS Lambda
        lbl_lam = QLabel(f"WLS Lambda: {self.wls_lambda:.0f}")
        slider_lam = QSlider(Qt.Horizontal)
        slider_lam.setRange(100, 20000)
        slider_lam.setValue(int(self.wls_lambda))

        def on_lam_change(val):
            self.wls_lambda = float(val)
            lbl_lam.setText(f"WLS Lambda: {self.wls_lambda:.0f}")
            self.rebuild_matchers()

        slider_lam.valueChanged.connect(on_lam_change)

        # Max Depth
        lbl_dep = QLabel(f"Max Depth (m): {self.max_depth:.1f}")
        slider_dep = QSlider(Qt.Horizontal)
        slider_dep.setRange(1, 30)
        slider_dep.setValue(int(self.max_depth))

        def on_dep_change(val):
            self.max_depth = float(val)
            lbl_dep.setText(f"Max Depth (m): {self.max_depth:.1f}")

        slider_dep.valueChanged.connect(on_dep_change)

        # Dodanie elementów do układu
        layout.addWidget(lbl_bs)
        layout.addWidget(slider_bs)
        layout.addWidget(lbl_nd)
        layout.addWidget(slider_nd)
        layout.addWidget(lbl_lam)
        layout.addWidget(slider_lam)
        layout.addWidget(lbl_dep)
        layout.addWidget(slider_dep)

    def rebuild_matchers(self):
        num_disp = 16 * self.num_disp_multiplier
        bs = self.block_size
        
        self.stereo_matcher = cv2.StereoSGBM_create(
            minDisparity=self.min_disp, 
            numDisparities=num_disp, 
            blockSize=bs,
            P1=8 * 3 * bs ** 2, 
            P2=32 * 3 * bs ** 2,
            disp12MaxDiff=1, 
            uniquenessRatio=10, 
            speckleWindowSize=100,
            speckleRange=32, 
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )
        self.right_matcher = cv2.ximgproc.createRightMatcher(self.stereo_matcher)
        self.wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_left=self.stereo_matcher)
        self.wls_filter.setLambda(self.wls_lambda)
        self.wls_filter.setSigmaColor(self.wls_sigma)

    def process(self, data):
        left, right, f, b = data.get('left'), data.get('right'), data.get('f'), data.get('baseline')
        
        if left is None or right is None or f is None or b is None:
            self.context['depth_visual'] = None
            data['depth_map'] = None
            return

        gray_left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        disp_left = self.stereo_matcher.compute(gray_left, gray_right)
        disp_right = self.right_matcher.compute(gray_right, gray_left)
        filtered_disp = self.wls_filter.filter(disp_left, gray_left, disparity_map_right=disp_right)
        
        disparity_float = filtered_disp.astype(np.float32) / 16.0
        with np.errstate(divide='ignore', invalid='ignore'):
            depth_map = (f * b) / disparity_float
            depth_map[disparity_float <= 0.0] = 0

        min_depth = 0.1
        invalid_mask = (depth_map <= 0.0) | (depth_map > self.max_depth)
        depth_clipped = np.clip(depth_map, min_depth, self.max_depth)
        
        data['depth_map'] = depth_clipped
        
        depth_visual = (255.0 * (1.0 - (depth_clipped - min_depth) / (self.max_depth - min_depth))).astype(np.float32)
        depth_visual[invalid_mask] = 0
        
        depth_visual_uint8 = np.clip(depth_visual, 0, 255).astype(np.uint8)
        self.context['depth_visual'] = cv2.cvtColor(depth_visual_uint8, cv2.COLOR_GRAY2BGR)

    def draw(self, data):
        return self.context.get('depth_visual', None)