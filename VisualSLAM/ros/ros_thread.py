import json
import threading
import traceback

import rclpy
from PySide6.QtCore import QThread, Signal
from rclpy.node import Node

from layer.depth_config import StereoDepthConfig
from layer.pipeline import LayerGraph
from ros.bridge_controller import ROS2BridgeController
from labels import LABEL_ROS_BRIDGE_STOPPED


class ROSThread(QThread):
    """Qt worker hosting the ROS bridge controller and its event loop."""

    pipeline_signal = Signal(dict)

    def __init__(self, layers, graph=None):
        super().__init__()
        self.layers = layers
        self.graph = graph if graph is not None else LayerGraph(layers)
        self.node = None
        self.bridge = None
        self.is_paused = False
        self.depth_config = next(
            (layer.depth_config for layer in layers if hasattr(layer, "depth_config")),
            StereoDepthConfig(),
        )
        self._runtime_lock = threading.Lock()
        self._runtime_active = False
        self._runtime_revision = None
        self._runtime_payload = ""
        self._runtime_signature = None
        self._next_revision = 0

    def set_runtime_configuration(self, active):
        config = self.depth_config
        if not config.validate():
            return
        serialized_config = json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":"))
        with self._runtime_lock:
            active = bool(active)
            was_active = self._runtime_active
            activation_changed = active and not was_active
            changed = serialized_config != self._runtime_signature
            self._runtime_active = active
            initial_configuration = self._runtime_revision is None
            configuration_should_be_sent = initial_configuration or changed or activation_changed
            deactivation_should_be_sent = was_active and not active
            if configuration_should_be_sent or deactivation_should_be_sent:
                self._next_revision += 1
                self._runtime_signature = serialized_config
                self._runtime_revision = self._next_revision
                self._runtime_payload = json.dumps(
                    {
                        **config.to_dict(),
                        "gt_enabled": active,
                        "revision": self._runtime_revision,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )

    def runtime_state(self):
        with self._runtime_lock:
            return {
                "active": self._runtime_active,
                "revision": self._runtime_revision,
                "payload": self._runtime_payload,
                "config": self.depth_config.to_dict(),
            }

    def run(self):
        try:
            self.node = Node("pyside_stereo_node")
            self.set_runtime_configuration(self._runtime_active)
            self.bridge = ROS2BridgeController(
                node=self.node,
                graph=self.graph,
                frame_callback=self.pipeline_signal.emit,
                runtime_state_callback=self.runtime_state,
                is_paused_callback=lambda: self.is_paused,
            )
            while rclpy.ok() and not self.isInterruptionRequested():
                rclpy.spin_once(self.node, timeout_sec=0.05)
                self.bridge.publish_pending_configuration()
        except Exception as error:
            details = traceback.format_exc()
            print(LABEL_ROS_BRIDGE_STOPPED.format(f"{error}\n{details}"))
        finally:
            if self.node is not None:
                self.node.destroy_node()
                self.node = None
                self.bridge = None
