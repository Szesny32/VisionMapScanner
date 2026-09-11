import cv2
import numpy as np
from collections import defaultdict
from layer.base_layer import BaseLayer

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    print("[OSTRZEŻENIE] Brak biblioteki 'numba'. Zainstaluj 'pip install numba' dla maksymalnej liczby FPS w podglądzie 3D!")
    
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return args[0] if len(args) == 1 and callable(args[0]) else decorator


# =====================================================================
# KOMPILOWANA FUNKCJA RENDERUJĄCA Z Z-BUFFEREM (Brak Overdraw, O(N))
# =====================================================================
@njit(fastmath=True, boundscheck=False, nogil=True, cache=True)
def fast_render_zbuffer(canvas, z_buffer, u, v, z_depth, sizes, colors, h, w):
    n_points = len(u)
    for i in range(n_points):
        px = u[i]
        py = v[i]
        size = sizes[i]
        z = z_depth[i]
        
        y2 = py + size
        if y2 > h: y2 = h
        x2 = px + size
        if x2 > w: x2 = w
        
        r, g, b = colors[i, 0], colors[i, 1], colors[i, 2]
        
        if size <= 1:
            if 0 <= py < h and 0 <= px < w:
                # Sprawdzenie Z-Buffera
                if z < z_buffer[py, px]:
                    z_buffer[py, px] = z
                    canvas[py, px, 0] = r
                    canvas[py, px, 1] = g
                    canvas[py, px, 2] = b
        else:
            for yy in range(py, y2):
                if 0 <= yy < h: 
                    for xx in range(px, x2):
                        if 0 <= xx < w:
                            # Sprawdzenie Z-Buffera dla każdego piksela klocka
                            if z < z_buffer[yy, xx]:
                                z_buffer[yy, xx] = z
                                canvas[yy, xx, 0] = r
                                canvas[yy, xx, 1] = g
                                canvas[yy, xx, 2] = b


class OctreeLayer(BaseLayer):
    def __init__(self):
        super().__init__("3D Point Cloud View")
        self.inputs = ["depth_map", "left", "f", "baseline", "robot_pose"]
        self.max_depth = 12.0
        self.base_voxel_size = 0.03
        self.max_map_radius = 12.0
        self.hits_to_solid = 3         
        self.pending_ttl = 2           
        self.solid_ttl = 100           
        self.merge_threshold = 6       
        
        self.pending_grid = {} 
        self.solid_l0 = {} 
        self.solid_l1 = {} 
        
        self.frame_count = 0
        self.uv_grid = None
        self.uv_shape = None

    def process(self, data):
        self.frame_count += 1
        
        f = data.get('f', 500.0)
        baseline = data.get('baseline', 0.1)
        robot_pose = data.get('robot_pose', {'x': 0.0, 'y': 0.0, 'theta': 0.0})
        depth_map = data.get(self._input_key('depth_map'), None)
        color_img = data.get('left', None)

        if color_img is not None:
            h, w = color_img.shape[:2]
        elif depth_map is not None:
            h, w = depth_map.shape
        else:
            h, w = 720, 1080

        cx, cy = w / 2.0, h / 2.0
        rx, ry = robot_pose['x'], robot_pose['y']
        theta = robot_pose.get('theta', 0.0)
        cos_t, sin_t = np.cos(theta), np.sin(theta)

        if depth_map is not None:
            step = 4 
            
            if self.uv_grid is None or self.uv_shape != (h, w):
                self.uv_grid = np.mgrid[0:h:step, 0:w:step]
                self.uv_shape = (h, w)
            
            v_coords, u_coords = self.uv_grid
            
            Z = depth_map[0:h:step, 0:w:step].astype(np.float32)
            
            # OPTYMALIZACJA PAMIĘCI MASOWEJ: In-place bitwise operations
            valid_mask = Z > 0.2
            valid_mask &= (Z < self.max_depth)
            
            Z_valid = Z[valid_mask]
            
            if len(Z_valid) > 0:
                u_valid = u_coords[valid_mask]
                v_valid = v_coords[valid_mask]
                
                f_inv = 1.0 / f
                X_cam = (u_valid - cx) * Z_valid * f_inv - (baseline / 2.0)
                Y_cam = (v_valid - cy) * Z_valid * f_inv
                
                global_X = Z_valid * cos_t + X_cam * sin_t + rx
                global_Y = Z_valid * sin_t - X_cam * cos_t + ry
                global_Z = -Y_cam

                dist_mask = np.abs(global_X - rx) <= self.max_map_radius
                dist_mask &= (np.abs(global_Y - ry) <= self.max_map_radius)
                
                global_X = global_X[dist_mask]
                global_Y = global_Y[dist_mask]
                global_Z = global_Z[dist_mask]
                
                if color_img is not None:
                    colors_raw = color_img[0:h:step, 0:w:step][valid_mask]
                else:
                    colors_raw = np.full((len(Z_valid), 3), 255, dtype=np.uint8)
                
                colors_valid = colors_raw[dist_mask]

                inv_voxel_size = 1.0 / self.base_voxel_size
                vx = (global_X * inv_voxel_size).astype(np.int32)
                vy = (global_Y * inv_voxel_size).astype(np.int32)
                vz = (global_Z * inv_voxel_size).astype(np.int32)

                if len(vx) > 0:
                    coords_stacked = np.column_stack((vx, vy, vz))
                    
                    coords_contiguous = np.ascontiguousarray(coords_stacked)
                    void_dtype = np.dtype((np.void, coords_contiguous.dtype.itemsize * 3))
                    coords_view = coords_contiguous.view(void_dtype)
                    
                    _, unique_indices = np.unique(coords_view, return_index=True)
                    
                    unique_coords = coords_stacked[unique_indices]
                    unique_colors = colors_valid[unique_indices]
                    parent_coords = unique_coords // 2

                    # OPTYMALIZACJA ITERACJI: Używamy zip() jako natywnego iteratora C
                    u_coords_list = unique_coords.tolist()
                    p_coords_list = parent_coords.tolist()
                    u_colors_list = unique_colors.tolist()

                    for u_coord, p_coord, color in zip(u_coords_list, p_coords_list, u_colors_list):
                        solid_key = tuple(u_coord)
                        parent_key = tuple(p_coord)
                        
                        if parent_key in self.solid_l1:
                            self.solid_l1[parent_key][3] = self.frame_count 
                            continue

                        if solid_key in self.solid_l0:
                            self.solid_l0[solid_key][3] = self.frame_count 
                            continue

                        if solid_key in self.pending_grid:
                            voxel = self.pending_grid[solid_key]
                            voxel[3] += 1
                            voxel[4] = self.frame_count
                            
                            if voxel[3] >= self.hits_to_solid:
                                self.solid_l0[solid_key] = [color[0], color[1], color[2], self.frame_count]
                                del self.pending_grid[solid_key]
                        else:
                            self.pending_grid[solid_key] = [color[0], color[1], color[2], 1, self.frame_count]

        # ---------------------------------------------------------
        # FAZA 3: Zoptymalizowany Garbage Collector
        # ---------------------------------------------------------
        rx_v, ry_v = int(rx / self.base_voxel_size), int(ry / self.base_voxel_size)
        max_dist = int(self.max_map_radius / self.base_voxel_size)

        if self.frame_count % 5 == 0:
            fc = self.frame_count
            pttl = self.pending_ttl
            dead_pending = [k for k, v in self.pending_grid.items() if fc - v[4] > pttl]
            for k in dead_pending:
                del self.pending_grid[k]

        if self.frame_count % 15 == 0:
            fc = self.frame_count
            sttl = self.solid_ttl
            keys_to_del_l0 = []
            
            # OPTYMALIZACJA GC: Szybki słownik tworzący listy domyślnie
            level_0_parents = defaultdict(list)
            
            for k, data in self.solid_l0.items():
                x, y, z = k
                if (fc - data[3] > sttl) or (abs(x - rx_v) > max_dist) or (abs(y - ry_v) > max_dist):
                    keys_to_del_l0.append(k)
                else:
                    level_0_parents[(x // 2, y // 2, z // 2)].append((k, data))

            for k in keys_to_del_l0:
                del self.solid_l0[k]

            keys_to_del_l1 = [k for k, data in self.solid_l1.items()
                              if (fc - data[3] > sttl) or 
                              (abs(k[0]*2 - rx_v) > max_dist) or (abs(k[1]*2 - ry_v) > max_dist)]
            for k in keys_to_del_l1:
                del self.solid_l1[k]

            for p_coords, children in level_0_parents.items():
                l = len(children)
                if l >= self.merge_threshold:
                    r = g = b = 0
                    max_ttl = 0
                    for child_k, data in children:
                        r += data[0]
                        g += data[1]
                        b += data[2]
                        if data[3] > max_ttl: max_ttl = data[3]
                        del self.solid_l0[child_k]
                    
                    self.solid_l1[p_coords] = [r // l, g // l, b // l, max_ttl]

        # ---------------------------------------------------------
        # FAZA 4: Renderowanie Masowe
        # ---------------------------------------------------------
        display_canvas = np.zeros((h, w, 3), dtype=np.uint8)
        
        # Inicjalizacja Z-Buffera nieskończonością (1e6)
        z_buffer = np.full((h, w), 1e6, dtype=np.float32)
        
        len_l0 = len(self.solid_l0)
        len_l1 = len(self.solid_l1)

        if len_l0 > 0 or len_l1 > 0:
            coords_list = []
            colors_list = []
            sizes_list = []

            if len_l0 > 0:
                k_l0 = np.array(list(self.solid_l0.keys()), dtype=np.int32)
                v_l0 = np.array([v[:3] for v in self.solid_l0.values()], dtype=np.uint8)
                coords_list.append((k_l0 + 0.5) * self.base_voxel_size)
                colors_list.append(v_l0)
                sizes_list.append(np.full(len_l0, self.base_voxel_size, dtype=np.float32))

            if len_l1 > 0:
                k_l1 = np.array(list(self.solid_l1.keys()), dtype=np.int32)
                v_l1 = np.array([v[:3] for v in self.solid_l1.values()], dtype=np.uint8)
                coords_list.append((k_l1 + 0.5) * (self.base_voxel_size * 2))
                colors_list.append(v_l1)
                sizes_list.append(np.full(len_l1, self.base_voxel_size * 2, dtype=np.float32))

            coords = np.vstack(coords_list)
            colors = np.vstack(colors_list)
            real_sizes = np.concatenate(sizes_list)
            
            coords[:, 0] -= rx
            coords[:, 1] -= ry
            
            x_base_local = coords[:, 0] * cos_t + coords[:, 1] * sin_t
            y_base_local = -coords[:, 0] * sin_t + coords[:, 1] * cos_t

            local_Z = x_base_local
            local_X = -y_base_local + (baseline / 2.0)
            local_Y = -coords[:, 2]

            valid_mask = local_Z > 0.1
            
            if np.any(valid_mask):
                local_X = local_X[valid_mask]
                local_Y = local_Y[valid_mask]
                local_Z = local_Z[valid_mask]
                valid_colors = colors[valid_mask]
                valid_sizes = real_sizes[valid_mask]

                z_inv = f / local_Z
                
                u = (local_X * z_inv + cx).astype(np.int32)
                v = (local_Y * z_inv + cy).astype(np.int32)
                box_sizes = np.clip((valid_sizes * z_inv).astype(np.int32), 1, 8)

                screen_mask = (u >= -8) & (u < w + 8) & (v >= -8) & (v < h + 8)
                
                if np.any(screen_mask):
                    u = u[screen_mask]
                    v = v[screen_mask]
                    final_colors = valid_colors[screen_mask]
                    z_depth = local_Z[screen_mask]
                    sizes = box_sizes[screen_mask]

                    # USUNIĘTO np.argsort! Podajemy po prostu surowe tablice, 
                    # Z-Buffer samodzielnie ustali, co jest na wierzchu, robiąc to znacznie szybciej.
                    fast_render_zbuffer(
                        display_canvas, 
                        z_buffer, 
                        u, v, z_depth, 
                        sizes, final_colors, 
                        h, w
                    )

        info = f"Solid: {len_l0 + len_l1} | Pending: {len(self.pending_grid)}"
        status = " (JIT ON)" if HAS_NUMBA else " (JIT OFF)"
        cv2.putText(display_canvas, info + status, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(display_canvas, f"Octree L0: {len_l0} | L1: {len_l1}", (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        self.context['octree_visual'] = display_canvas

    def draw(self, data):
        return self.context.get('octree_visual', None)