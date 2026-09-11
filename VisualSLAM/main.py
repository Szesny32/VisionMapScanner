import sys
import rclpy
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QPushButton,
    QGroupBox,
)

from ros.ros_thread import ROSThread
from gui.image_tile import ImageTile

from layer.camera_layer import CameraLayer
from layer.stereo_layer import StereoLayer
from layer.keypoint_layer import KeypointLayer
from layer.octree_layer import OctreeLayer
from layer.occupancy_grid_layer import OccupancyGridLayer
from constants import LAYERS_CONFIG, WINDOW_WIDTH, WINDOW_HEIGHT, LABEL_PAUSE, LABEL_LAYERS_SETTINGS


class MainWindow(QMainWindow):
    def __init__(self, ros_thread):
        super().__init__()
        self.ros_thread = ros_thread
        self.layers = self.ros_thread.layers
        self.tiles = {}

        self._apply_config_to_layers()
        self.setWindowTitle("ROS2 PySide Pipeline Studio")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._init_ui()
        self.rebuild_grid()
        self.ros_thread.pipeline_signal.connect(self.update_viewports)
        self.ros_thread.start()

    def _apply_config_to_layers(self):
        for layer in self.layers:
            cfg_key = None
            if layer.name in LAYERS_CONFIG:
                cfg_key = layer.name
            elif layer.__class__.__name__ in LAYERS_CONFIG:
                cfg_key = layer.__class__.__name__

            if cfg_key:
                cfg = LAYERS_CONFIG[cfg_key]
                layer.enabled = cfg.get("enabled", getattr(layer, "enabled", True))
                layer.grid_span = cfg.get("grid_span", getattr(layer, "grid_span", 1))
                layer.inputs = cfg.get("inputs", getattr(layer, "inputs", []))
                
                params = cfg.get("params", {})
                for k, v in params.items():
                    if hasattr(layer, k):
                        setattr(layer, k, v)

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        left_layout = self._create_left_panel()
        right_layout = self._create_right_panel()

        main_layout.addLayout(left_layout, stretch=3)
        main_layout.addLayout(right_layout, stretch=1)

    def _create_left_panel(self) -> QVBoxLayout:
        left_layout = QVBoxLayout()
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_widget)
        left_layout.addWidget(scroll, stretch=5)

        ctrl_layout = QHBoxLayout()
        self.btn_toggle = QPushButton(LABEL_PAUSE)
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.clicked.connect(self.toggle_pipeline)
        ctrl_layout.addWidget(self.btn_toggle)
        left_layout.addLayout(ctrl_layout, stretch=1)

        return left_layout

    def _create_right_panel(self) -> QVBoxLayout:
        right_layout = QVBoxLayout()
        right_group = QGroupBox(LABEL_LAYERS_SETTINGS)
        right_group_layout = QVBoxLayout(right_group)
        
        scroll_right = QScrollArea()
        scroll_right.setWidgetResizable(True)
        container_right = QWidget()
        container_right_layout = QVBoxLayout(container_right)

        for layer in self.layers:
            control_widget = layer.create_control_widget(on_toggle_callback=self.rebuild_grid)
            container_right_layout.addWidget(control_widget)

        container_right_layout.addStretch()
        scroll_right.setWidget(container_right)
        right_group_layout.addWidget(scroll_right)
        right_layout.addWidget(right_group)

        return right_layout

    @Slot(dict)
    def update_viewports(self, draw_results):
        for layer_name, img in draw_results.items():
            if layer_name in self.tiles:
                self.tiles[layer_name].update_image(img)

    def rebuild_grid(self):
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        self.tiles.clear()
        active = [l for l in self.layers if l.enabled]
        
        row, col = 0, 0
        for layer in active:
            tile = ImageTile(layer.name)
            self.tiles[layer.name] = tile
            
            span = getattr(layer, 'grid_span', 1)
            
            if span == 2:
                if col > 0:
                    row += 1
                    col = 0
                self.grid_layout.addWidget(tile, row, col, 1, 2)
                row += 1
                col = 0
            else:
                self.grid_layout.addWidget(tile, row, col)
                col += 1
                if col > 1:
                    col = 0
                    row += 1

    def toggle_pipeline(self):
        self.ros_thread.is_paused = self.btn_toggle.isChecked()
        self.btn_toggle.setText("Wznów" if self.ros_thread.is_paused else "Pauza")

    def closeEvent(self, event):
        if hasattr(self, 'ros_thread') and self.ros_thread.isRunning():
            self.ros_thread.requestInterruption()
            self.ros_thread.quit()
            self.ros_thread.wait(1000)
            
        if rclpy.ok():
            rclpy.shutdown()
            
        event.accept()


if __name__ == '__main__':
    rclpy.init(args=sys.argv)
    app = QApplication(sys.argv)


    layers = [
        CameraLayer("Left Camera", "left"),
        CameraLayer("Right Camera", "right"),
        StereoLayer(),
        KeypointLayer(),
        OctreeLayer(),
        OccupancyGridLayer(),
    ]

    ros_thread = ROSThread(layers=layers)

    window = MainWindow(ros_thread)
    window.show()

    exit_code = app.exec()
    
    if rclpy.ok():
        rclpy.shutdown()
        
    sys.exit(exit_code)