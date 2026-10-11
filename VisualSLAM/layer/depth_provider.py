from abc import ABC, abstractmethod

import numpy as np


class DepthProvider(ABC):
    """Common output contract for OpenCV and Unity ground-truth providers."""

    output_dtype = np.float32
    output_units = "m"

    @staticmethod
    def normalize_depth_map(depth):
        if depth is None:
            return None
        try:
            result = np.asarray(depth)
        except (TypeError, ValueError):
            return None
        if result.size == 0:
            return None
        if result.ndim == 3 and result.shape[2] == 1:
            result = result[:, :, 0]
        if result.ndim != 2:
            return None
        try:
            return np.asarray(result, dtype=np.float32)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def stereo_support_mask(depth, focal_length, baseline, min_disparity, num_disparities):
        """Return the shared left/right image overlap used for source comparison."""
        depth = DepthProvider.normalize_depth_map(depth)
        if depth is None:
            return None
        try:
            focal_length = float(focal_length)
            baseline = float(baseline)
            min_disparity = int(min_disparity)
            num_disparities = int(num_disparities)
        except (TypeError, ValueError, OverflowError):
            return None
        if (not np.isfinite(focal_length) or not np.isfinite(baseline)
                or focal_length <= 0 or baseline <= 0):
            return None

        height, width = depth.shape
        x_coordinates = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width))
        first_valid_x = max(0, min_disparity + num_disparities)
        support = x_coordinates >= first_valid_x
        valid_depth = np.isfinite(depth) & (depth > 0.0)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            disparity = (focal_length * baseline) / depth
        support &= ~valid_depth | (x_coordinates >= disparity)
        return support

    @staticmethod
    def postprocess_depth_map(depth, min_depth, max_depth, support_mask=None):
        """Sanitize, mask and cap a depth map while preserving zero as no measurement."""
        result = DepthProvider.normalize_depth_map(depth)
        if result is None:
            return None
        try:
            min_depth = float(min_depth)
            max_depth = float(max_depth)
        except (TypeError, ValueError, OverflowError):
            return None
        if (not np.isfinite(min_depth) or not np.isfinite(max_depth)
                or min_depth < 0.0 or max_depth <= min_depth):
            return None

        result = result.copy()
        valid = np.isfinite(result) & (result > 0.0)
        if support_mask is not None:
            try:
                support_mask = np.asarray(support_mask, dtype=bool)
            except (TypeError, ValueError):
                return None
            if support_mask.shape != result.shape:
                return None
            valid &= support_mask
        result[~valid] = 0.0
        result[valid] = np.clip(result[valid], min_depth, max_depth)
        return result.astype(np.float32, copy=False)

    @staticmethod
    def depth_statistics(depth):
        """Summarize raw or processed depth values without retaining frame buffers."""
        result = DepthProvider.normalize_depth_map(depth)
        if result is None:
            return {"empty": True}
        finite = np.isfinite(result)
        valid = finite & (result > 0.0)
        values = result[valid]
        stats = {
            "empty": False,
            "pixels": int(result.size),
            "zero": int(np.count_nonzero(result == 0.0)),
            "nonfinite": int(np.count_nonzero(~finite)),
            "valid": int(values.size),
        }
        if values.size:
            percentiles = np.percentile(values, (50, 90, 99))
            stats.update({
                "min": float(values.min()),
                "max": float(values.max()),
                "p50": float(percentiles[0]),
                "p90": float(percentiles[1]),
                "p99": float(percentiles[2]),
            })
        return stats

    @abstractmethod
    def process(self, data):
        raise NotImplementedError
