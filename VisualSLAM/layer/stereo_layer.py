import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QSlider
from PySide6.QtCore import Qt
from layer.base_layer import BaseLayer, depth_to_visual
from layer.depth_config import StereoDepthConfig
from layer.depth_provider import DepthProvider

SGBM_MODE = getattr(cv2, "STEREO_SGBM_MODE_HH4", cv2.STEREO_SGBM_MODE_HH)

class StereoLayer(BaseLayer, DepthProvider):
    def __init__(self, depth_config=None):
        super().__init__("Stereo & Depth")
        self.depth_config = depth_config or StereoDepthConfig()
        self.outputs = ["depth_map"]
        self.provides = {"depth_map": "depth_map"}
        self.min_disp = self.depth_config.min_disp
        self.num_disp_multiplier = self.depth_config.num_disp_multiplier
        self.block_size = self.depth_config.block_size
        self.p2_scale = self.depth_config.p2_scale
        self.wls_lambda = self.depth_config.wls_lambda
        self.wls_sigma = self.depth_config.wls_sigma
        self.stereo_matcher = None
        self.right_matcher = None
        self.wls_filter = None
        self.rebuild_matchers()

    @property
    def num_disp_multiplier(self):
        return self.depth_config.num_disp_multiplier

    @num_disp_multiplier.setter
    def num_disp_multiplier(self, value):
        self.depth_config.num_disp_multiplier = int(value)

    @property
    def block_size(self):
        return self.depth_config.block_size

    @block_size.setter
    def block_size(self, value):
        self.depth_config.block_size = int(value)

    @property
    def p2_scale(self):
        return self.depth_config.p2_scale

    @p2_scale.setter
    def p2_scale(self, value):
        self.depth_config.p2_scale = float(value)

    @property
    def wls_lambda(self):
        return self.depth_config.wls_lambda

    @wls_lambda.setter
    def wls_lambda(self, value):
        self.depth_config.wls_lambda = float(value)

    @property
    def wls_sigma(self):
        return self.depth_config.wls_sigma

    @wls_sigma.setter
    def wls_sigma(self, value):
        self.depth_config.wls_sigma = float(value)

    @property
    def min_depth(self):
        return self.depth_config.min_depth

    @min_depth.setter
    def min_depth(self, value):
        self.depth_config.min_depth = float(value)

    @property
    def max_depth(self):
        return self.depth_config.max_depth

    @max_depth.setter
    def max_depth(self, value):
        self.depth_config.max_depth = float(value)

    def _build_custom_controls(self, layout):
        # Minimum disparity
        lbl_min_disp = QLabel(f"Minimum Disparity: {self.min_disp}")
        slider_min_disp = QSlider(Qt.Horizontal)
        slider_min_disp.setRange(-16, 16)
        slider_min_disp.setValue(self.min_disp)

        def on_min_disp_change(value):
            self.min_disp = value
            lbl_min_disp.setText(f"Minimum Disparity: {self.min_disp}")
            self.rebuild_matchers()
            self.notify_config_changed()

        slider_min_disp.valueChanged.connect(on_min_disp_change)

        # Block Size
        lbl_bs = QLabel(f"Block Size: {self.block_size}")
        slider_bs = QSlider(Qt.Horizontal)
        slider_bs.setRange(1, 11)
        slider_bs.setValue((self.block_size - 1) // 2)

        def on_bs_change(val):
            self.block_size = 2 * val + 1
            lbl_bs.setText(f"Block Size: {self.block_size}")
            self.rebuild_matchers()
            self.depth_config.block_size = self.block_size
            self.notify_config_changed()

        slider_bs.valueChanged.connect(on_bs_change)

        # SGBM P2 smoothness penalty scale
        lbl_p2 = QLabel(f"SGBM P2 Scale: {self.p2_scale:.1f}")
        slider_p2 = QSlider(Qt.Horizontal)
        slider_p2.setRange(1, 160)
        slider_p2.setValue(int(round(self.p2_scale * 10)))

        def on_p2_scale_change(value):
            self.p2_scale = value / 10.0
            lbl_p2.setText(f"SGBM P2 Scale: {self.p2_scale:.1f}")
            self.rebuild_matchers()
            self.notify_config_changed()

        slider_p2.valueChanged.connect(on_p2_scale_change)

        # Num Disparities
        lbl_nd = QLabel(f"Num Disparities: {16 * self.num_disp_multiplier}")
        slider_nd = QSlider(Qt.Horizontal)
        slider_nd.setRange(1, 16)
        slider_nd.setValue(self.num_disp_multiplier)

        def on_nd_change(val):
            self.num_disp_multiplier = val
            lbl_nd.setText(f"Num Disparities: {16 * val}")
            self.rebuild_matchers()
            self.depth_config.num_disp_multiplier = val
            self.notify_config_changed()

        slider_nd.valueChanged.connect(on_nd_change)

        # WLS Lambda
        lbl_lam = QLabel(f"WLS Lambda: {self.wls_lambda:.0f}")
        slider_lam = QSlider(Qt.Horizontal)
        slider_lam.setRange(100, 100000)
        slider_lam.setValue(int(self.wls_lambda))

        def on_lam_change(val):
            self.wls_lambda = float(val)
            lbl_lam.setText(f"WLS Lambda: {self.wls_lambda:.0f}")
            self.rebuild_matchers()
            self.depth_config.wls_lambda = self.wls_lambda
            self.notify_config_changed()

        slider_lam.valueChanged.connect(on_lam_change)

        # WLS Sigma
        lbl_sigma = QLabel(f"WLS Sigma: {self.wls_sigma:.1f}")
        slider_sigma = QSlider(Qt.Horizontal)
        slider_sigma.setRange(1, 100)
        slider_sigma.setValue(int(round(self.wls_sigma * 10)))

        def on_sigma_change(value):
            self.wls_sigma = value / 10.0
            lbl_sigma.setText(f"WLS Sigma: {self.wls_sigma:.1f}")
            self.rebuild_matchers()
            self.notify_config_changed()

        slider_sigma.valueChanged.connect(on_sigma_change)

        # Dodanie elementów do układu
        layout.addWidget(lbl_min_disp)
        layout.addWidget(slider_min_disp)
        layout.addWidget(lbl_bs)
        layout.addWidget(slider_bs)
        layout.addWidget(lbl_p2)
        layout.addWidget(slider_p2)
        layout.addWidget(lbl_nd)
        layout.addWidget(slider_nd)
        layout.addWidget(lbl_lam)
        layout.addWidget(slider_lam)
        layout.addWidget(lbl_sigma)
        layout.addWidget(slider_sigma)

    def rebuild_matchers(self):
        num_disp = 16 * self.num_disp_multiplier
        bs = self.block_size
        
        self.stereo_matcher = cv2.StereoSGBM_create(
            minDisparity=self.min_disp, 
            numDisparities=num_disp, 
            blockSize=bs,
            P1=8 * 3 * bs ** 2, 
            P2=int(32 * 3 * bs ** 2 * self.p2_scale),
            disp12MaxDiff=1, 
            uniquenessRatio=10, 
            speckleWindowSize=100,
            speckleRange=32, 
            mode=SGBM_MODE
        )
        self.right_matcher = cv2.ximgproc.createRightMatcher(self.stereo_matcher)
        self.wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_left=self.stereo_matcher)
        self.wls_filter.setLambda(self.wls_lambda)
        self.wls_filter.setSigmaColor(self.wls_sigma)
        self.depth_config.min_disp = self.min_disp
        self.depth_config.num_disp_multiplier = self.num_disp_multiplier
        self.depth_config.block_size = self.block_size
        self.depth_config.wls_lambda = self.wls_lambda
        self.depth_config.wls_sigma = self.wls_sigma

    def process(self, data):
        left = data.get("left")
        right = data.get("right")
        focal_length = data.get("f")
        baseline = data.get("baseline")

        try:
            focal_length = float(focal_length)
            baseline = float(baseline)
            if left is None or right is None or np.asarray(left).size == 0 or np.asarray(right).size == 0:
                raise ValueError("Camera image is missing or empty")
        except (TypeError, ValueError):
            self.context['depth_visual'] = None
            data['depth_map'] = None
            return

        if not np.isfinite(focal_length) or not np.isfinite(baseline) or focal_length <= 0 or baseline <= 0:
            self.context['depth_visual'] = None
            data['depth_map'] = None
            return

        try:
            gray_left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
            gray_right = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
        except (cv2.error, TypeError, ValueError):
            self.context["depth_visual"] = None
            data["depth_map"] = None
            return

        if gray_left.shape != gray_right.shape or self.stereo_matcher is None:
            self.context["depth_visual"] = None
            data["depth_map"] = None
            return

        try:
            disp_left = self.stereo_matcher.compute(gray_left, gray_right)
            disp_right = self.right_matcher.compute(gray_right, gray_left)
            filtered_disp = self.wls_filter.filter(disp_left, gray_left, disparity_map_right=disp_right)
        except (cv2.error, AttributeError, TypeError, ValueError):
            self.context["depth_visual"] = None
            data["depth_map"] = None
            return

        if (filtered_disp is None or np.asarray(filtered_disp).size == 0
                or np.asarray(filtered_disp).shape != gray_left.shape):
            self.context["depth_visual"] = None
            data["depth_map"] = None
            return
        
        disparity_float = filtered_disp.astype(np.float32) / 16.0
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            raw_depth_map = (focal_length * baseline) / disparity_float
        raw_depth_map[disparity_float <= 0.0] = 0.0
        support_mask = self.stereo_support_mask(
            raw_depth_map,
            focal_length,
            baseline,
            self.min_disp,
            16 * self.num_disp_multiplier,
        )
        depth_map = self.postprocess_depth_map(
            raw_depth_map,
            self.min_depth,
            self.max_depth,
            support_mask,
        )
        data["depth_map"] = depth_map
        if data.get("_collect_depth_diagnostics", False):
            data.setdefault("_depth_diagnostics", {})["opencv"] = {
                "filtered_disparity": self._disparity_statistics(disparity_float),
                "before_mask": self.depth_statistics(raw_depth_map),
                "masked_pixels": (
                    int(np.count_nonzero(~support_mask)) if support_mask is not None else 0
                ),
                "supported_pixels": (
                    int(np.count_nonzero(support_mask)) if support_mask is not None else 0
                ),
                "after_mask": self.depth_statistics(depth_map),
                "range_histogram": self._depth_range_histogram(
                    raw_depth_map, self.min_depth, self.max_depth
                ),
            }

        if depth_map is None:
            self.context["depth_visual"] = None
            return
        depth_visual = depth_to_visual(depth_map, self.min_depth, self.max_depth)
        self.context['depth_visual'] = cv2.cvtColor(depth_visual, cv2.COLOR_GRAY2BGR)

    def draw(self, data):
        return self.context.get('depth_visual', None)

    @staticmethod
    def _disparity_statistics(disparity):
        values = np.asarray(disparity, dtype=np.float32)
        valid = np.isfinite(values) & (values > 0.0)
        valid_values = values[valid]
        if valid_values.size == 0:
            return {
                "valid": 0,
                "invalid": int(values.size),
                "nonfinite": int(np.count_nonzero(~np.isfinite(values))),
            }
        percentiles = np.percentile(valid_values, (1, 50, 90, 99))
        return {
            "valid": int(valid_values.size),
            "invalid": int(np.count_nonzero(~valid)),
            "nonfinite": int(np.count_nonzero(~np.isfinite(values))),
            "min_px": float(np.min(valid_values)),
            "max_px": float(np.max(valid_values)),
            "p01_px": float(percentiles[0]),
            "p50_px": float(percentiles[1]),
            "p90_px": float(percentiles[2]),
            "p99_px": float(percentiles[3]),
        }

    @staticmethod
    def _depth_range_histogram(depth, min_depth, max_depth, bins=10):
        values = np.asarray(depth, dtype=np.float32)
        valid_values = values[np.isfinite(values) & (values > 0.0)]
        edges = np.linspace(min_depth, max_depth, bins + 1)
        counts, _ = np.histogram(valid_values, bins=edges)
        return {
            "edges_m": [float(value) for value in edges],
            "counts": [int(value) for value in counts],
            "below_min": int(np.count_nonzero(valid_values < min_depth)),
            "above_max": int(np.count_nonzero(valid_values > max_depth)),
        }
