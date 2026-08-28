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
        
        self.left_img = None
        self.right_img = None
        self.left_stamp = 0.0
        self.right_stamp = 0.0
        
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
        
        self.get_logger().info('Advanced node with WLS filter launched.')

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

        dt = abs(self.left_stamp - self.right_stamp)
        if dt > 0.001:
            return

        left = self.left_img
        right = self.right_img
        self.left_img = None
        self.right_img = None
         
        gray_left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        # gray_left = clahe.apply(gray_left)
        # gray_right = clahe.apply(gray_right)

        disp_left = self.stereo_matcher.compute(gray_left, gray_right)
        disp_right = self.right_matcher.compute(gray_right, gray_left)

        filtered_disp = self.wls_filter.filter(disp_left, gray_left, disparity_map_right=disp_right)
        
        disparity_float = filtered_disp.astype(np.float32) / 16.0

        disp_visual = cv2.normalize(
            disparity_float, None, alpha=0, beta=255,
            norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U
        )

        cv2.imshow("Left Camera", left)
        cv2.imshow("Disparity Map (WLS)", disp_visual)
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