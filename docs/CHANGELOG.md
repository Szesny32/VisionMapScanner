## 29/08/2027 
- **Added Core Utilities & Architecture:**
    - Added new utility systems: FileManager, Config, Logger, and ShellManager.
    - Implemented dynamic Git root path resolution to make configuration paths relative to the repository root instead of absolute user paths.
- **Changed Automated the Run Workflow:** 
  - Simplified launching the project. There is no longer any need to manually execute `run_ros_tcp_endpoint.sh` and `run_stereo_processor_node.sh` in separate terminal windows.
  - From now on, **it is enough to simply run the project in Unity** (`StereoVision Scene`). Unity automatically launches all required ROS2 processes in the background and safely closes them (along with their child processes) when exiting Play mode.