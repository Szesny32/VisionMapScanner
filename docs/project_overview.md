
Building a Visual SLAM system.

Running a synthetic ground truth data source from Unity (including camera feed and scene pose)

# 1. System Architecture and Data Pipeline

- **Communication Layer (ROS2):** ROS-TCP-Connector
- **Unity (Source):** The simulator publishes synchronized ROS2 messages:
    - (sensor_msgs/Image)
        - `/stereo/camera_left`
        - `/stereo/camera_right`
            
    - (geometry_msgs/PoseStamped)
        - `/robot/pose` – ideal pose for validating SLAM algorithms.
            
- **Python (Receiver / Pipeline):** The main loop processes each frame sequentially through defined layers.
    
#### Layer-Pipeline Architecture
Each frame and its metadata pass through modular processing layers:

```python
def run_pipeline(frame_id, frame):
	for layer in active_layers():
		layer.process(frame)
	for layer in active_layers():
		frame = layer.draw(frame)	
```

- **Phase 1: Data Ingestion**
    - Configuring ROS-TCP-Connector in Unity for ROS2.
    - Python subscriber script receiving the stereo stream + ground truth.
    - Format conversion using `cv_bridge`.
        
- **Phase 2: Preprocessing (Front-End)**
    - **Rectification:** Distortion correction and stereo baseline alignment.
    - **Keypoints Extraction & Matching:** Feature detection (e.g., ORB, AKAZE, SuperPoint) and matching them between the left and right cameras (depth estimation) as well as between frames ($t-1$ to $t$).
    - **Visual Odometry (VO):** Calculating relative camera motion based on feature transformations (PnP / Epipolar Geometry).
        
- **Phase 3: Advanced SLAM and Backend**
    - **Kalman Filter (EKF):** Fusion of visual odometry data with raw position/velocity (optional IMU from Unity).
    - **Loop Closing:** Detection of previously visited locations (e.g., using a Bag of Words database – DBoW2/DBoW3).
    - **Backend Optimization:** Pose-graph optimization (e.g., g2o or GTSAM) to reduce accumulating error (drift).
        
- **Phase 4: Map Representation (Octree)**
    - **Point Cloud:** Generating 3D data from stereo (`cv2.reprojectImageTo3D`).
    - **Octree Structure:** Aggregation and compression of the point cloud into a spatial tree structure (e.g., utilizing the `octomap` library or a custom implementation in Python/C++) for efficient memory and collision management.