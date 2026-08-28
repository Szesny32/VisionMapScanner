import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np
import cv2

class StereoViewerNode(Node):
    def __init__(self):
        super().__init__('stereo_viewer_node')
        
        self.sub_left = self.create_subscription(
            Image, '/stereo/camera_left', self.listener_callback_left, 10)
        self.sub_right = self.create_subscription(
            Image, '/stereo/camera_right', self.listener_callback_right, 10)
        
        self.get_logger().info('The stereo vision listener node has launched... ')

    def listener_callback_left(self, msg):
        self.process_and_show_image(msg, "Left Camera")

    def listener_callback_right(self, msg):
        self.process_and_show_image(msg, "Right Camera")

    def process_and_show_image(self, msg, window_name):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if cv_image is not None:
                cv2.imshow(window_name, cv_image)
                cv2.waitKey(1)  
            else:
                self.get_logger().warn(f"The image could not be decoded for{window_name}")

        except Exception as e:
            self.get_logger().error(f"Image processing error: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = StereoViewerNode()
    
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