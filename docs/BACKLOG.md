# Backlog

## 1. Layering System & Data Source Selection (Top Priority) [DONE]
* **Data Source Selection (Layering)**: Enable input source selection at each processing step via UI/configuration (e.g., `Select List`).
  * *Example*: Point cloud generation must allow selecting between Ground Truth (GT) depth map or an algorithm/network-computed depth map.
* **Caching Verification**: Ensure that if a lower-level layer has already been generated or computed, processing is skipped and cached results are reused (verify existing implementation).

## 2. GT Stereovision from Unity (Legacy Code Audit & Refactor)
* **Code Review & Analysis**: Locate and analyze the existing legacy script in the Unity directory.
* **Perspective Verification**: Verify script functionality and clarify which perspective is generated (left camera, right camera, or center/baseline midpoint) - The redesigned code must be adapted to the system.

## 3. GT Point Cloud from Unity
* **Global Point Cloud**: Generate a 3D point cloud for a bounded environment area.
* **Camera-Centric Point Cloud**: Generate a point cloud strictly from the camera's view frustum and perspective.

## 4. GT Nav Map from Unity
* **Ground Truth Navigation Map**: Generate a navigation map (Occupancy Grid Map) directly from the Unity environment as a baseline.

## 5. Metrics & Comparison Module (GT vs. Algorithm)
* **Performance Evaluation**: Implement quantitative metrics (e.g., MSE, MAE, Chamfer Distance, IoU) comparing Ground Truth layers with algorithm-computed outputs at various pipeline stages.

## 6. Historical Metrics Tracking
* **Run Metadata & Context**: Attach execution metadata to every metric run, including Git commit hash, branch name, algorithm/model version, timestamp, and environment configuration.
* **Metrics Persistence & Storage**: Implement a persistence mechanism (e.g., SQLite/PostgreSQL, MLflow, or versioned JSON/CSV evaluation artifacts) to log metrics long-term.
* **Trend Analysis & Regressions**: Enable historical querying to plot performance trends over time, catch quality regressions, and compare new run results directly against historical baseline commits.

## 7. Testing Suite & CI/CD Pipeline
* **High Code Coverage**: Implement unit, integration, and system tests targeting **>90% code coverage** across the codebase.
* **Automated Metric Threshold Gates**: Add automated pass/fail tests in the pipeline that trigger build failures if algorithm metrics drop below specified quality thresholds (regression testing).
---

# Future / Experimental Backlog

## 6. CNN Calibration
* **Goal**: Calibrate camera parameters and disparity estimation.
* **Method**: Use Unity with parametrically varied camera properties (e.g., baseline, focal length) for model training and calibration.