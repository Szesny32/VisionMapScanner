import cv2
import numpy as np
import rclpy
import math
from rclpy.node import Node
from PySide6.QtCore import QThread, Signal
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PoseStamped

class ROSThread(QThread):
    pipeline_signal = Signal(dict)

    def __init__(self, layers):
        super().__init__()
        self.layers = layers
        self.node = None
        self.is_paused = False

        self.left_img = None
        self.right_img = None
        self.left_stamp = 0.0
        self.right_stamp = 0.0
        self.focal_length = None
        self.baseline = None
        self.robot_pose = {'x': 0.0, 'y': 0.0, 'theta': 0.0}

    def run(self):
        try:
            self.node = Node('pyside_stereo_node')
            
            self.node.create_subscription(Image, '/stereo/camera_left', self.left_cb, 10)
            self.node.create_subscription(Image, '/stereo/camera_right', self.right_cb, 10)
            self.node.create_subscription(CameraInfo, '/stereo/left/camera_info', self.info_l_cb, 10)
            self.node.create_subscription(CameraInfo, '/stereo/right/camera_info', self.info_r_cb, 10)
            self.node.create_subscription(PoseStamped, '/robot/pose', self.pose_cb, 10)

            while rclpy.ok() and not self.isInterruptionRequested():
                rclpy.spin_once(self.node, timeout_sec=0.1)
                
        except Exception as e:
            print(f"Wątek ROS2 zatrzymany: {e}")
        finally:
            if self.node:
                self.node.destroy_node()

    def info_l_cb(self, msg):
        self.focal_length = msg.p[0]

    def info_r_cb(self, msg):
        if self.focal_length and self.focal_length > 0:
            self.baseline = -msg.p[3] / self.focal_length

    def left_cb(self, msg):
        self.left_img = self.msg_to_cv2(msg)
        self.left_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.try_trigger()

    def right_cb(self, msg):
        self.right_img = self.msg_to_cv2(msg)
        self.right_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.try_trigger()

    def msg_to_cv2(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return cv_image
        except Exception as e:
            print(f"Błąd dekodowania JPEG z ROS: {e}")
            return None

    def try_trigger(self):
        if self.is_paused or self.left_img is None or self.right_img is None:
            return

        left = self.left_img
        right = self.right_img
        self.left_img = None
        self.right_img = None

        frame_id = getattr(self, '_frame_counter', 0) + 1
        self._frame_counter = frame_id

        frame_data = {
            'frame_id': frame_id,
            'left': left,
            'right': right,
            'f': self.focal_length if self.focal_length else 500.0,
            'baseline': self.baseline if self.baseline else 0.1,
            'robot_pose': self.robot_pose
        }

        active = [l for l in self.layers if l.enabled]
        
        for layer in active:
            layer.process(frame_data)
            
        draw_results = {layer.name: layer.draw(frame_data) for layer in active}
        self.pipeline_signal.emit(draw_results)
    
    def pose_cb(self, msg):
        # UNITY AXIS -> ROS
        # Unity: Z = front, X = right, Y = up
        # ROS:   X = front, Y = left,  Z = up
        
        px = msg.pose.position.z   
        py = -msg.pose.position.x 

        qx = msg.pose.orientation.x
        qy = msg.pose.orientation.y
        qz = msg.pose.orientation.z
        qw = msg.pose.orientation.w

        siny = 2.0 * (qw * qy + qz * qx)
        cosy = 1.0 - 2.0 * (qx * qx + qy * qy)
        unity_yaw = math.atan2(siny, cosy)

        theta = -unity_yaw

        self.robot_pose = {'x': px, 'y': py, 'theta': theta}