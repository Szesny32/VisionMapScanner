import cv2
import numpy as np
from layer.base_layer import BaseLayer, depth_to_visual
from layer.depth_config import StereoDepthConfig
from layer.depth_provider import DepthProvider

class GTDepthLayer(BaseLayer, DepthProvider):
    def __init__(self, depth_config=None):
        super().__init__("GT Depth (Unity)")
        self.depth_config = depth_config or StereoDepthConfig()
        self.outputs = ["depth_map_gt"]
        self.provides = {"depth_map": "depth_map_gt"}
        self.topic = "/stereo/camera_depth"

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

    def process(self, data):
        depth = self.normalize_depth_map(data.get("depth_map_gt"))
        f = data.get("f")
        b = data.get("baseline")

        if depth is None:
            self.context["gt_depth_visual"] = None
            data["depth_map_gt"] = None
            return

        left_image = data.get("left")
        if left_image is not None:
            try:
                expected_shape = np.asarray(left_image).shape[:2]
            except (TypeError, ValueError):
                expected_shape = None
            if expected_shape is not None and len(expected_shape) == 2 and depth.shape != expected_shape:
                self.context["gt_depth_visual"] = None
                data["depth_map_gt"] = None
                return

        depth_proc = depth.copy().astype(np.float32, copy=False)
        depth_proc[~np.isfinite(depth_proc)] = 0.0
        h, w = depth_proc.shape

        # The stereo overlap mask is meaningful only with complete camera metadata.
        try:
            focal_length = float(f)
            baseline = float(b)
            has_camera_calibration = (
                np.isfinite(focal_length) and np.isfinite(baseline)
                and focal_length > 0 and baseline > 0
            )
        except (TypeError, ValueError):
            has_camera_calibration = False

        if has_camera_calibration:
            x_grid = np.broadcast_to(np.arange(w), (h, w))
            num_disp = max(
                0,
                16 * self.depth_config.num_disp_multiplier + self.depth_config.min_disp,
            )
            invalid_mask = x_grid < num_disp
            with np.errstate(divide='ignore', invalid='ignore'):
                disparity_gt = np.where(depth_proc > 0, (focal_length * baseline) / depth_proc, 0)
            invalid_mask |= (x_grid < disparity_gt)
            depth_proc[invalid_mask] = 0.0

        valid_mask = depth_proc > 0
        depth_proc[valid_mask] = np.clip(depth_proc[valid_mask], self.min_depth, self.max_depth)
        data["depth_map_gt"] = np.asarray(depth_proc, dtype=np.float32)

        depth_visual = depth_to_visual(depth_proc, self.min_depth, self.max_depth)
        self.context["gt_depth_visual"] = cv2.cvtColor(depth_visual, cv2.COLOR_GRAY2BGR)

    def draw(self, data):
        return self.context.get("gt_depth_visual", None)
