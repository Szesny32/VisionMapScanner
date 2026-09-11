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

from layer.pipeline import LayerGraph
from utility.load_layers_from_json import load_layers_from_json
from utility.config_io import update_layer_sources
from constants import GUI_CONFIG_PATH, WINDOW_WIDTH, WINDOW_HEIGHT, LABEL_PAUSE, LABEL_LAYERS_SETTINGS


class MainWindow(QMainWindow):
    def __init__(self, ros_thread):
        super().__init__()
        self.ros_thread = ros_thread
        self.layers = self.ros_thread.layers
        self.graph = self.ros_thread.graph
        self.tiles = {}

        self.setWindowTitle("ROS2 PySide Pipeline Studio")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._init_ui()
        self.rebuild_grid()
        self.ros_thread.pipeline_signal.connect(self.update_viewports)
        self.ros_thread.start()

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
            layer.settings_saver = self._save_sources
            control_widget = layer.create_control_widget(
                on_toggle_callback=self.rebuild_grid, graph=self.graph
            )
            container_right_layout.addWidget(control_widget)

        container_right_layout.addStretch()
        scroll_right.setWidget(container_right)
        right_group_layout.addWidget(scroll_right)
        right_layout.addWidget(right_group)

        return right_layout

    def _save_sources(self, layer):
        update_layer_sources(GUI_CONFIG_PATH, layer)

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

    layers = load_layers_from_json(GUI_CONFIG_PATH)
    graph = LayerGraph(layers)

    ros_thread = ROSThread(layers=layers, graph=graph)

    window = MainWindow(ros_thread)
    window.show()

    exit_code = app.exec()
    
    if rclpy.ok():
        rclpy.shutdown()
        
    sys.exit(exit_code)