import json
import math
import threading
import time
import traceback
from collections import deque

import cv2
import numpy as np
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from layer.depth_provider import DepthProvider


class ROS2BridgeController:
    """Owns ROS transport and assembles synchronized camera frames for the pipeline."""

    LEFT_TOPIC = "/stereo/camera_left"
    RIGHT_TOPIC = "/stereo/camera_right"
    DEPTH_TOPIC = "/stereo/camera_depth"
    LEFT_INFO_TOPIC = "/stereo/left/camera_info"
    RIGHT_INFO_TOPIC = "/stereo/right/camera_info"
    POSE_TOPIC = "/robot/pose"
    CONFIG_TOPIC = "/stereo/config"
    CONFIG_READY_TOPIC = "/stereo/config_ready"
    CONFIG_READY_ACK_TOPIC = "/stereo/config_ready_ack"
    CONFIG_ACK_TOPIC = "/stereo/config_ack"
    SYNC_TOLERANCE_SEC = 0.001
    CONFIG_RETRY_SEC = 1.0
    MAX_PENDING_STEREO_FRAMES = 4
    MAX_BUFFERED_DEPTH_FRAMES = 8
    DIAGNOSTICS_FRAME_INTERVAL = 60

    def __init__(
        self,
        node,
        graph,
        frame_callback,
        runtime_state_callback,
        is_paused_callback,
    ):
        self.node = node
        self.graph = graph
        self.frame_callback = frame_callback
        self.runtime_state_callback = runtime_state_callback
        self.is_paused_callback = is_paused_callback
        self.left_image = None
        self.right_image = None
        self.left_stamp = None
        self.right_stamp = None
        self.focal_length = None
        self.baseline = None
        self.left_camera_info = None
        self.right_camera_info = None
        self.depth_frames = deque(maxlen=self.MAX_BUFFERED_DEPTH_FRAMES)
        self.pending_stereo_frames = deque()
        self.robot_pose = {"x": 0.0, "y": 0.0, "theta": 0.0}
        self.frame_counter = 0
        self.processed_frame_count = 0
        self.pipeline_error_count = 0
        self.invalid_image_count = 0
        self.invalid_depth_count = 0
        self.missing_gt_count = 0
        self.invalid_metadata_count = 0
        self.unsynchronized_frame_count = 0
        self.last_stereo_stamp = None
        self.last_depth_stamp = None
        self.last_depth_diagnostics = None
        self._last_diagnostics_time = time.monotonic()
        self._config_publisher = node.create_publisher(String, self.CONFIG_TOPIC, 10)
        self._ready_ack_publisher = node.create_publisher(String, self.CONFIG_READY_ACK_TOPIC, 10)
        self._subscriptions = [
            node.create_subscription(Image, self.LEFT_TOPIC, self.left_image_callback, 10),
            node.create_subscription(Image, self.RIGHT_TOPIC, self.right_image_callback, 10),
            node.create_subscription(Image, self.DEPTH_TOPIC, self.depth_image_callback, 10),
            node.create_subscription(CameraInfo, self.LEFT_INFO_TOPIC, self.left_info_callback, 10),
            node.create_subscription(CameraInfo, self.RIGHT_INFO_TOPIC, self.right_info_callback, 10),
            node.create_subscription(PoseStamped, self.POSE_TOPIC, self.pose_callback, 10),
            node.create_subscription(String, self.CONFIG_READY_TOPIC, self.configuration_ready_callback, 10),
            node.create_subscription(String, self.CONFIG_ACK_TOPIC, self.configuration_ack_callback, 10),
        ]
        self._active_revision = None
        self._awaiting_revision = None
        self._last_publish_time = 0.0
        self._ack_lock = threading.Lock()
        self._acknowledged_revision = None

    @staticmethod
    def stamp_seconds(stamp):
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9

    @classmethod
    def _camera_info_metadata(cls, message):
        try:
            header = message.header
            return {
                "width": int(message.width),
                "height": int(message.height),
                "distortion_model": str(message.distortion_model),
                "d": [float(value) for value in message.d],
                "k": [float(value) for value in message.k],
                "r": [float(value) for value in message.r],
                "p": [float(value) for value in message.p],
                "stamp": cls.stamp_seconds(header.stamp),
                "frame_id": str(header.frame_id),
            }
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None

    def left_info_callback(self, message):
        try:
            focal_length = float(message.p[0])
            if math.isfinite(focal_length) and focal_length > 0:
                self.focal_length = focal_length
                self.left_camera_info = self._camera_info_metadata(message)
                return
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            pass
        self.invalid_metadata_count += 1

    def right_info_callback(self, message):
        try:
            translation = float(message.p[3])
            if self.focal_length is not None and self.focal_length > 0 and math.isfinite(translation):
                baseline = -translation / self.focal_length
                if math.isfinite(baseline) and baseline > 0:
                    self.baseline = baseline
                    self.right_camera_info = self._camera_info_metadata(message)
                    return
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            pass
        self.invalid_metadata_count += 1

    @staticmethod
    def image_message_to_depth(message):
        try:
            if message.height <= 0 or message.width <= 0 or not message.data:
                return None
            if message.encoding == "32FC1":
                values = np.frombuffer(message.data, dtype=np.float32)
                if values.size != int(message.height) * int(message.width):
                    return None
                return values.reshape(message.height, message.width).copy()
            if message.encoding in ("16UC1", "mono16"):
                values = np.frombuffer(message.data, dtype=np.uint16)
                if values.size != int(message.height) * int(message.width):
                    return None
                return values.reshape(message.height, message.width).astype(np.float32) * 0.001
            decoded = cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if decoded is None or decoded.size == 0:
                return None
            return np.asarray(decoded, dtype=np.float32)
        except (TypeError, ValueError, BufferError, cv2.error):
            return None

    @staticmethod
    def image_message_to_bgr(message):
        try:
            if not message.data:
                return None
            encoded = np.frombuffer(message.data, dtype=np.uint8)
            decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if decoded is None or decoded.size == 0:
                return None
            if message.height > 0 and message.width > 0 and decoded.shape[:2] != (message.height, message.width):
                return None
            return decoded
        except (TypeError, ValueError, BufferError, cv2.error):
            return None

    def depth_image_callback(self, message):
        depth_map = self.image_message_to_depth(message)
        try:
            depth_stamp = self.stamp_seconds(message.header.stamp)
        except (AttributeError, TypeError, ValueError, OverflowError):
            self.invalid_depth_count += 1
            return
        if depth_map is None:
            self.invalid_depth_count += 1
        self.last_depth_stamp = depth_stamp
        self.depth_frames.append((depth_stamp, depth_map))
        self.process_pending_stereo_frames()

    def left_image_callback(self, message):
        self.left_image = self.image_message_to_bgr(message)
        self.left_stamp = self._read_image_stamp(message, self.left_image)
        self.try_process_synchronized_frame()

    def right_image_callback(self, message):
        self.right_image = self.image_message_to_bgr(message)
        self.right_stamp = self._read_image_stamp(message, self.right_image)
        self.try_process_synchronized_frame()

    def _read_image_stamp(self, message, image):
        if image is None:
            self.invalid_image_count += 1
        try:
            stamp = self.stamp_seconds(message.header.stamp)
            return stamp if math.isfinite(stamp) else None
        except (AttributeError, TypeError, ValueError, OverflowError):
            self.invalid_image_count += 1
            return None

    def try_process_synchronized_frame(self):
        if self.is_paused_callback() or self.left_image is None or self.right_image is None:
            return
        if self.left_stamp is None or self.right_stamp is None:
            return
        if not math.isfinite(self.left_stamp) or not math.isfinite(self.right_stamp):
            self.left_image = self.right_image = None
            self.left_stamp = self.right_stamp = None
            self.unsynchronized_frame_count += 1
            return
        if abs(self.left_stamp - self.right_stamp) > self.SYNC_TOLERANCE_SEC:
            if self.left_stamp < self.right_stamp:
                self.left_image = self.left_stamp = None
            else:
                self.right_image = self.right_stamp = None
            self.unsynchronized_frame_count += 1
            return
        if self.left_image.shape[:2] != self.right_image.shape[:2]:
            self.left_image = self.right_image = None
            self.left_stamp = self.right_stamp = None
            self.invalid_image_count += 2
            return

        stereo_stamp = (self.left_stamp + self.right_stamp) * 0.5
        left, right = self.left_image, self.right_image
        self.left_image = self.right_image = None
        self.left_stamp = self.right_stamp = None
        self.frame_counter += 1
        candidate = {
            "frame_id": self.frame_counter,
            "stamp": stereo_stamp,
            "left": left,
            "right": right,
        }
        self.pending_stereo_frames.append(candidate)
        self.process_pending_stereo_frames()

    def process_pending_stereo_frames(self):
        runtime_state = self.runtime_state_callback()
        while self.pending_stereo_frames:
            match_index = self._find_depth_frame_index(self.pending_stereo_frames[0]["stamp"])
            if match_index >= 0:
                candidate = self.pending_stereo_frames.popleft()
                buffered_depth = list(self.depth_frames)
                depth_stamp, depth_map = buffered_depth.pop(match_index)
                self.depth_frames = deque(buffered_depth, maxlen=self.MAX_BUFFERED_DEPTH_FRAMES)
                candidate["depth_stamp"] = depth_stamp
                self._emit_stereo_frame(candidate, depth_map, runtime_state["config"])
                continue
            if not runtime_state["active"] or len(self.pending_stereo_frames) > self.MAX_PENDING_STEREO_FRAMES:
                self._emit_stereo_frame(self.pending_stereo_frames.popleft(), None, runtime_state["config"])
                continue
            break

    def _find_depth_frame_index(self, stereo_stamp):
        matching = [
            (index, abs(depth_stamp - stereo_stamp))
            for index, (depth_stamp, _depth_map) in enumerate(self.depth_frames)
            if abs(depth_stamp - stereo_stamp) <= self.SYNC_TOLERANCE_SEC
        ]
        return min(matching, key=lambda match: match[1])[0] if matching else -1

    def _emit_stereo_frame(self, candidate, depth_map, runtime_config):
        left = candidate["left"]
        right = candidate["right"]
        self.frame_counter = max(self.frame_counter, candidate["frame_id"])
        baseline = self.baseline if self.baseline is not None and self.baseline > 0 else float(
            runtime_config.get("baseline", 0.38)
        )
        focal_length = self.focal_length if self.focal_length is not None else 500.0
        frame = {
            "frame_id": candidate["frame_id"],
            "stamp": candidate["stamp"],
            "depth_stamp": candidate.get("depth_stamp"),
            "left": left,
            "right": right,
            "f": focal_length,
            "baseline": baseline,
            "_collect_depth_diagnostics": (
                candidate["frame_id"] % self.DIAGNOSTICS_FRAME_INTERVAL == 0
            ),
            "robot_pose": dict(self.robot_pose),
            "depth_map_gt": depth_map,
            "depth_config": runtime_config,
            "camera_info": {
                "focal_length": focal_length,
                "baseline": baseline,
                "width": left.shape[1],
                "height": left.shape[0],
                "depth_units": "m",
                "left": self.left_camera_info,
                "right": self.right_camera_info,
            },
        }
        if depth_map is None and runtime_config.get("gt_enabled", False):
            self.missing_gt_count += 1
        try:
            draw_results = self.graph.run(frame)
            processed_gt_map = frame.get("depth_map_gt")
            if (frame["_collect_depth_diagnostics"] and depth_map is not None
                    and processed_gt_map is not depth_map):
                raw_gt_statistics = DepthProvider.depth_statistics(depth_map)
                processed_gt_statistics = DepthProvider.depth_statistics(processed_gt_map)
                frame.setdefault("_depth_diagnostics", {})["unity_gt"] = {
                    "before_mask": raw_gt_statistics,
                    "masked_pixels": max(
                        0,
                        processed_gt_statistics.get("zero", 0)
                        - raw_gt_statistics.get("zero", 0),
                    ),
                    "after_mask": processed_gt_statistics,
                }
            self.frame_callback(draw_results)
            self.processed_frame_count += 1
            self.last_stereo_stamp = candidate["stamp"]
            if frame["_collect_depth_diagnostics"]:
                self.last_depth_diagnostics = {
                    "stamp": candidate["stamp"],
                    "depth_stamp": candidate.get("depth_stamp"),
                    "providers": frame.get("_depth_diagnostics", {}),
                    "camera_info": frame["camera_info"],
                    "depth_config": frame["depth_config"],
                }
        except Exception:
            self.pipeline_error_count += 1
            self.node.get_logger().error(
                "Frame %s at %.9f failed in the depth pipeline:\n%s"
                % (candidate["frame_id"], candidate["stamp"], traceback.format_exc())
            )

    def pose_callback(self, message):
        try:
            position = message.pose.position
            orientation = message.pose.orientation
            values = (position.z, position.x, orientation.w, orientation.y, orientation.z, orientation.x)
            if not all(math.isfinite(float(value)) for value in values):
                raise ValueError("pose contains non-finite values")
            sin_yaw = 2.0 * (orientation.w * orientation.y + orientation.z * orientation.x)
            cos_yaw = 1.0 - 2.0 * (orientation.x ** 2 + orientation.y ** 2)
            self.robot_pose = {
                "x": float(position.z),
                "y": -float(position.x),
                "theta": -math.atan2(sin_yaw, cos_yaw),
            }
        except (AttributeError, TypeError, ValueError, OverflowError):
            self.invalid_metadata_count += 1

    def configuration_ready_callback(self, _message):
        state = self.runtime_state_callback()
        ready_ack = String()
        ready_ack.data = "ready"
        self._ready_ack_publisher.publish(ready_ack)
        if state["revision"] is not None:
            self._publish_configuration(state)

    def configuration_ack_callback(self, message):
        try:
            revision = int(json.loads(message.data).get("revision", -1))
        except (TypeError, ValueError, AttributeError):
            return
        with self._ack_lock:
            self._acknowledged_revision = revision

    def publish_pending_configuration(self):
        state = self.runtime_state_callback()
        revision = state["revision"]
        if revision is None:
            self._active_revision = None
            self._awaiting_revision = None
            self._publish_diagnostics_if_due()
            return
        if revision != self._active_revision:
            self._active_revision = revision
            self._awaiting_revision = revision
            self._publish_configuration(state)
            return
        with self._ack_lock:
            acknowledged = self._acknowledged_revision
        if acknowledged == self._awaiting_revision:
            self._awaiting_revision = None
        elif self._awaiting_revision is not None:
            now = self.node.get_clock().now().nanoseconds * 1e-9
            if now - self._last_publish_time >= self.CONFIG_RETRY_SEC:
                self._publish_configuration(state)
        self.process_pending_stereo_frames()
        self._publish_diagnostics_if_due()

    def _publish_diagnostics_if_due(self):
        now = time.monotonic()
        if now - self._last_diagnostics_time < 5.0:
            return
        self._last_diagnostics_time = now
        depth_diagnostics = self._format_depth_diagnostics(self.last_depth_diagnostics)
        self.node.get_logger().info(
            "Stereo bridge: processed=%d pipeline_errors=%d invalid_images=%d "
            "invalid_depth=%d missing_gt=%d invalid_metadata=%d unsynchronized=%d "
            "last_stereo_stamp=%s last_depth_stamp=%s depth_comparison=%s"
            % (
                self.processed_frame_count,
                self.pipeline_error_count,
                self.invalid_image_count,
                self.invalid_depth_count,
                self.missing_gt_count,
                self.invalid_metadata_count,
                self.unsynchronized_frame_count,
                self.last_stereo_stamp,
                self.last_depth_stamp,
                depth_diagnostics,
            )
        )

    @staticmethod
    def _format_depth_diagnostics(diagnostics):
        if not diagnostics:
            return "unavailable"
        details = []
        for provider_name, phases in diagnostics.get("providers", {}).items():
            phase_details = []
            for phase_name in ("before_mask", "after_mask"):
                stats = phases.get(phase_name, {})
                if stats.get("empty"):
                    phase_details.append("%s=empty" % phase_name)
                    continue
                phase_details.append(
                    "%s[min=%.3f max=%.3f p50=%.3f p90=%.3f p99=%.3f "
                    "zero=%d nonfinite=%d valid=%d masked=%d]"
                    % (
                        phase_name,
                        stats.get("min", 0.0),
                        stats.get("max", 0.0),
                        stats.get("p50", 0.0),
                        stats.get("p90", 0.0),
                        stats.get("p99", 0.0),
                        stats.get("zero", 0),
                        stats.get("nonfinite", 0),
                        stats.get("valid", 0),
                        phases.get("masked_pixels", 0),
                    )
                )
            provider_details = list(phase_details)
            disparity = phases.get("filtered_disparity")
            if disparity:
                provider_details.append(
                    "disparity[valid=%d invalid=%d p01=%.2f p50=%.2f p90=%.2f p99=%.2f px]"
                    % (
                        disparity.get("valid", 0),
                        disparity.get("invalid", 0),
                        disparity.get("p01_px", 0.0),
                        disparity.get("p50_px", 0.0),
                        disparity.get("p90_px", 0.0),
                        disparity.get("p99_px", 0.0),
                    )
                )
            histogram = phases.get("range_histogram")
            if histogram:
                provider_details.append(
                    "range_bins=%s below_min=%d above_max=%d"
                    % (
                        histogram.get("counts", []),
                        histogram.get("below_min", 0),
                        histogram.get("above_max", 0),
                    )
                )
            details.append("%s{%s}" % (provider_name, ",".join(provider_details)))
        depth_stamp = diagnostics.get("depth_stamp")
        stamp_details = "stereo_stamp=%.9f" % diagnostics["stamp"]
        if depth_stamp is not None:
            stamp_details += " gt_stamp=%.9f delta_ms=%.3f" % (
                depth_stamp,
                abs(depth_stamp - diagnostics["stamp"]) * 1000.0,
            )
        camera_info = diagnostics.get("camera_info", {})
        depth_config = diagnostics.get("depth_config", {})
        metadata_details = ""
        if camera_info:
            metadata_details += " f=%.2fpx baseline=%.4fm" % (
                camera_info.get("focal_length", 0.0),
                camera_info.get("baseline", 0.0),
            )
        if depth_config:
            metadata_details += " configured_range=[%.3f,%.3f]m" % (
                depth_config.get("min_depth", 0.0),
                depth_config.get("max_depth", 0.0),
            )
        return "%s%s %s" % (stamp_details, metadata_details, " ".join(details))

    def _publish_configuration(self, state):
        message = String()
        message.data = state["payload"]
        self._config_publisher.publish(message)
        self._awaiting_revision = state["revision"]
        self._last_publish_time = self.node.get_clock().now().nanoseconds * 1e-9
