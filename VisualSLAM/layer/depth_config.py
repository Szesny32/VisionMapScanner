from dataclasses import asdict, dataclass
import json
import math


@dataclass
class StereoDepthConfig:
    """Runtime settings shared by stereo depth providers and the Unity bridge."""

    min_depth: float = 0.1
    max_depth: float = 10.0
    width: int = 1080
    height: int = 720
    baseline: float = 0.38
    min_disp: int = 0
    num_disp_multiplier: int = 8
    block_size: int = 5
    p2_scale: float = 1.2
    wls_lambda: float = 8000.0
    wls_sigma: float = 1.5

    def to_dict(self):
        return asdict(self)

    def to_json(self, revision):
        payload = self.to_dict()
        payload["revision"] = revision
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def validate(self):
        try:
            return (
                math.isfinite(self.min_depth)
                and math.isfinite(self.max_depth)
                and math.isfinite(self.baseline)
                and math.isfinite(self.wls_lambda)
                and math.isfinite(self.wls_sigma)
                and math.isfinite(self.p2_scale)
                and self.min_depth > 0.0
                and self.max_depth > self.min_depth
                and 16 <= self.width <= 4096
                and 16 <= self.height <= 2160
                and 0.0 < self.baseline <= 5.0
                and -16 <= self.min_disp <= 16
                and 1 <= self.num_disp_multiplier <= 16
                and 3 <= self.block_size <= 23
                and self.block_size % 2 == 1
                and 0.25 <= self.p2_scale <= 16.0
                and 100.0 <= self.wls_lambda <= 100000.0
                and 0.1 <= self.wls_sigma <= 10.0
            )
        except (TypeError, ValueError, OverflowError):
            return False
