import cv2
import numpy as np
from layer.base_layer import BaseLayer

class GTDepthLayer(BaseLayer):
    def __init__(self):
        super().__init__("GT Depth (Unity)")
        self.outputs = ["depth_map_gt"]
        self.provides = {"depth_map": "depth_map_gt"}
        self.topic = "/stereo/camera_depth"
        self.min_depth = 0.1
        self.max_depth = 10.0

    def process(self, data):
        depth = data.get("depth_map_gt", None)
        data["depth_map_gt"] = depth

        self.context["gt_depth_visual"] = None
        if depth is None:
            return

        depth_clipped = np.clip(depth.astype(np.float32), self.min_depth, self.max_depth)
        depth_visual = (255.0 * (1.0 - (depth_clipped - self.min_depth) / (self.max_depth - self.min_depth))).astype(np.uint8)
        self.context["gt_depth_visual"] = cv2.cvtColor(depth_visual, cv2.COLOR_GRAY2BGR)

    def draw(self, data):
        return self.context.get("gt_depth_visual", None)