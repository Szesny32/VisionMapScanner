import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QSlider, QPushButton
from PySide6.QtCore import Qt
from layer.base_layer import BaseLayer

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*args, **kwargs):
        def decorator(func): return func
        return args[0] if len(args) == 1 and callable(args[0]) else decorator


@njit(fastmath=True, nogil=True, cache=True)
def update_grid_bresenham(grid, rx, ry, hits_x, hits_y, l_occ, l_free, min_l, max_l):
    h, w = grid.shape
    n_rays = len(hits_x)
    
    for i in range(n_rays):
        hx = hits_x[i]
        hy = hits_y[i]
        
        dx = abs(hx - rx)
        dy = -abs(hy - ry)
        sx = 1 if rx < hx else -1
        sy = 1 if ry < hy else -1
        err = dx + dy
        
        x, y = rx, ry
        
        while True:
            if 0 <= x < w and 0 <= y < h:
                if x == hx and y == hy:
                    grid[y, x] += l_occ
                    if grid[y, x] > max_l: grid[y, x] = max_l
                    break
                else:
                    grid[y, x] += l_free
                    if grid[y, x] < min_l: grid[y, x] = min_l
            else:
                break
            
            if x == hx and y == hy:
                break
                
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy


class OccupancyGridLayer(BaseLayer):
    def __init__(self):
        super().__init__("2D Occupancy Grid")
        self.inputs = ["depth_map", "f", "baseline", "robot_pose"]

        self.resolution = 0.05
        self.map_size = 1000
        self.offset_x = self.map_size // 2
        self.offset_y = self.map_size // 2
        
        self.l_occ = 0.85
        self.l_free = -0.4
        self.max_l = 3.5
        self.min_l = -2.0
        
        self.min_height = -0.2
        self.max_height = 1.0
        
        self.grid = np.zeros((self.map_size, self.map_size), dtype=np.float32)
        self.view_size = 600

    def _build_custom_controls(self, layout):
        # Suwak: Wysokość minimalna
        lbl_min_h = QLabel(f"Min Height: {self.min_height:.2f}m")
        slider_min_h = QSlider(Qt.Horizontal)
        slider_min_h.setRange(-10, 10)  # -1.0m do 1.0m
        slider_min_h.setValue(int(self.min_height * 10))

        def on_min_h_change(val):
            self.min_height = val / 10.0
            lbl_min_h.setText(f"Min Height: {self.min_height:.2f}m")

        slider_min_h.valueChanged.connect(on_min_h_change)

        # Suwak: Wysokość maksymalna
        lbl_max_h = QLabel(f"Max Height: {self.max_height:.2f}m")
        slider_max_h = QSlider(Qt.Horizontal)
        slider_max_h.setRange(0, 30)  # 0.0m do 3.0m
        slider_max_h.setValue(int(self.max_height * 10))

        def on_max_h_change(val):
            self.max_height = val / 10.0
            lbl_max_h.setText(f"Max Height: {self.max_height:.2f}m")

        slider_max_h.valueChanged.connect(on_max_h_change)

        # Przycisk: Czyszczenie mapy
        btn_clear = QPushButton("Resetuj Mapę")
        btn_clear.clicked.connect(self.clear_map)

        layout.addWidget(lbl_min_h)
        layout.addWidget(slider_min_h)
        layout.addWidget(lbl_max_h)
        layout.addWidget(slider_max_h)
        layout.addWidget(btn_clear)

    def clear_map(self):
        self.grid.fill(0.0)

    def process(self, data):
        f = data.get('f', 500.0)
        baseline = data.get('baseline', 0.1)
        robot_pose = data.get('robot_pose', {'x': 0.0, 'y': 0.0, 'theta': 0.0})
        depth_map = data.get(self._input_key('depth_map'), None)

        if depth_map is None:
            return

        h, w = depth_map.shape
        cx, cy = w / 2.0, h / 2.0
        rx, ry = robot_pose['x'], robot_pose['y']
        theta = robot_pose.get('theta', 0.0)
        cos_t, sin_t = np.cos(theta), np.sin(theta)

        step = 4
        v_coords, u_coords = np.mgrid[0:h:step, 0:w:step]
        Z = depth_map[0:h:step, 0:w:step].astype(np.float32)
        
        valid_mask = Z > 0.2
        valid_mask &= (Z < 8.0)
        
        Z_valid = Z[valid_mask]
        
        if len(Z_valid) > 0:
            u_valid = u_coords[valid_mask]
            v_valid = v_coords[valid_mask]
            
            f_inv = 1.0 / f
            X_cam = (u_valid - cx) * Z_valid * f_inv - (baseline / 2.0)
            Y_cam = (v_valid - cy) * Z_valid * f_inv
            
            global_Z = -Y_cam 
            
            height_mask = global_Z > self.min_height
            height_mask &= (global_Z < self.max_height)
            
            Z_filt = Z_valid[height_mask]
            X_cam_filt = X_cam[height_mask]
            
            global_X = Z_filt * cos_t + X_cam_filt * sin_t + rx
            global_Y = Z_filt * sin_t - X_cam_filt * cos_t + ry
            
            inv_res = 1.0 / self.resolution
            map_x = (global_X * inv_res + self.offset_x).astype(np.int32)
            map_y = (global_Y * inv_res + self.offset_y).astype(np.int32)
            
            rx_map = int(rx * inv_res + self.offset_x)
            ry_map = int(ry * inv_res + self.offset_y)
            
            bounds_mask = (map_x >= 0) & (map_x < self.map_size) & (map_y >= 0) & (map_y < self.map_size)
            map_x = map_x[bounds_mask]
            map_y = map_y[bounds_mask]
            
            if len(map_x) > 0:
                coords_stacked = np.column_stack((map_x, map_y))
                coords_contiguous = np.ascontiguousarray(coords_stacked)
                void_dtype = np.dtype((np.void, coords_contiguous.dtype.itemsize * 2))
                unique_coords = np.unique(coords_contiguous.view(void_dtype)).view(coords_contiguous.dtype).reshape(-1, 2)
                
                unique_x = unique_coords[:, 0]
                unique_y = unique_coords[:, 1]
                
                update_grid_bresenham(
                    self.grid, 
                    rx_map, ry_map, 
                    unique_x, unique_y, 
                    self.l_occ, self.l_free, 
                    self.min_l, self.max_l
                )

        display_grid = np.full((self.map_size, self.map_size), 127, dtype=np.uint8)
        display_grid[self.grid < 0.0] = 255
        display_grid[self.grid > 0.0] = 0
        
        rx_m = int(rx / self.resolution + self.offset_x)
        ry_m = int(ry / self.resolution + self.offset_y)
        
        half_v = self.view_size // 2
        
        x1 = max(0, rx_m - half_v)
        x2 = min(self.map_size, rx_m + half_v)
        y1 = max(0, ry_m - half_v)
        y2 = min(self.map_size, ry_m + half_v)
        
        roi = display_grid[y1:y2, x1:x2]
        canvas = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        
        rob_px = rx_m - x1
        rob_py = ry_m - y1
        
        cv2.circle(canvas, (rob_px, rob_py), 4, (0, 0, 255), -1)
        line_len = 15
        end_x = int(rob_px + np.cos(theta) * line_len)
        end_y = int(rob_py + np.sin(theta) * line_len)
        cv2.line(canvas, (rob_px, rob_py), (end_x, end_y), (0, 0, 255), 2)
        
        cv2.putText(canvas, f"Map Res: {self.resolution}m/px", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 0, 0), 1)
        
        self.context['occupancy_visual'] = canvas

    def draw(self, data):
        return self.context.get('occupancy_visual', None)