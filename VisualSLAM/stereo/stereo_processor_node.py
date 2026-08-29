import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PoseStamped
import numpy as np
import cv2

class StereoProcessorNode(Node):
    def __init__(self):
        super().__init__('stereo_processor_node')
        
        self.sub_left = self.create_subscription(
            Image, '/stereo/camera_left', self.left_image_callback, 10)
        self.sub_right = self.create_subscription(
            Image, '/stereo/camera_right', self.right_image_callback, 10) 
        self.sub_info_left = self.create_subscription(
            CameraInfo, '/stereo/left/camera_info', self.info_left_callback, 10)
        self.sub_info_right = self.create_subscription(
            CameraInfo, '/stereo/right/camera_info', self.info_right_callback, 10)
        
        self.left_img = None
        self.right_img = None
        self.left_stamp = 0.0
        self.right_stamp = 0.0
        self.focal_length = None
        self.baseline = None
        
        min_disp = 0
        num_disp = 16 * 8  # 128
        block_size = 5
        
        self.stereo_matcher = cv2.StereoSGBM_create(
            minDisparity=min_disp,
            numDisparities=num_disp,
            blockSize=block_size,
            P1=8 * 3 * block_size ** 2,
            P2=32 * 3 * block_size ** 2,
            disp12MaxDiff=1,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=32,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )
        
        self.right_matcher = cv2.ximgproc.createRightMatcher(self.stereo_matcher)
        self.wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_left=self.stereo_matcher)
        self.wls_filter.setLambda(8000.0)
        self.wls_filter.setSigmaColor(1.5)
        
        self.get_logger().info('Advanced node with WLS filter & Dynamic Depth Map launched.')

    def info_left_callback(self, msg):
        self.focal_length = msg.p[0]

    def info_right_callback(self, msg):
        if self.focal_length is not None and self.focal_length > 0:
            tx = msg.p[3]
            self.baseline = -tx / self.focal_length

    def left_image_callback(self, msg):
        img = self.msg_to_cv2(msg)
        if img is not None:
            self.left_img = img
            self.left_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            self.try_process_stereo()

    def right_image_callback(self, msg):
        img = self.msg_to_cv2(msg)
        if img is not None:
            self.right_img = img
            self.right_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            self.try_process_stereo()

    def msg_to_cv2(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            return None

    def try_process_stereo(self):
        if self.left_img is None or self.right_img is None:
            return
        if self.focal_length is None or self.baseline is None:
            return

        dt = abs(self.left_stamp - self.right_stamp)
        if dt > 0.001:
            return

        left = self.left_img
        right = self.right_img
        self.left_img = None
        self.right_img = None
         
        gray_left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        # TODO: clahe
        # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        # gray_left = clahe.apply(gray_left)
        # gray_right = clahe.apply(gray_right)

        disp_left = self.stereo_matcher.compute(gray_left, gray_right)
        disp_right = self.right_matcher.compute(gray_right, gray_left)

        filtered_disp = self.wls_filter.filter(disp_left, gray_left, disparity_map_right=disp_right)
        
        disparity_float = filtered_disp.astype(np.float32) / 16.0

        with np.errstate(divide='ignore', invalid='ignore'):
            depth_map = (self.focal_length * self.baseline) / disparity_float
            depth_map[disparity_float <= 0.0] = 0

        min_depth = 0.1   
        max_depth = 10.0  

        invalid_mask = (depth_map <= 0.0) | (depth_map > max_depth)
        depth_clipped = np.clip(depth_map, min_depth, max_depth)
        
        depth_visual = (255.0 * (1.0 - (depth_clipped - min_depth) / (max_depth - min_depth))).astype(np.uint8)
        depth_visual[invalid_mask] = 0

        cv2.imshow("Left Camera", left)
        cv2.imshow("Depth Map (Meters)", depth_visual)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = StereoProcessorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()