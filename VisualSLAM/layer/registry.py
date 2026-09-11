from layer.camera_layer import CameraLayer
from layer.stereo_layer import StereoLayer
from layer.keypoint_layer import KeypointLayer
from layer.octree_layer import OctreeLayer
from layer.occupancy_grid_layer import OccupancyGridLayer
from layer.gt_depth_layer import GTDepthLayer

LAYER_REGISTRY = {
    "CameraLayer": CameraLayer,
    "StereoLayer": StereoLayer,
    "KeypointLayer": KeypointLayer,
    "OctreeLayer": OctreeLayer,
    "OccupancyGridLayer": OccupancyGridLayer,
    "GTDepthLayer": GTDepthLayer,
}