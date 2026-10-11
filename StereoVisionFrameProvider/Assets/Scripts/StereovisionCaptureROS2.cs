using UnityEngine;
using UnityEngine.UI;
using System;
using System.IO;
using System.Collections.Generic;
using Unity.Collections;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Sensor;
using RosMessageTypes.Std;
using RosMessageTypes.Geometry;
using RosMessageTypes.BuiltinInterfaces;

public class StereovisionCaptureROS2 : MonoBehaviour
{
    Logger logger;
    private ROSConnection ros;

    [Header("Stereo Cameras")]
    public Camera cam1; 
    public Camera cam2;

    [Header("ROS Topics")]
    [SerializeField] private string topicNameLeft = "/stereo/camera_left";
    [SerializeField] private string topicNameRight = "/stereo/camera_right";
    [SerializeField] private string topicInfoLeft = "/stereo/left/camera_info";
    [SerializeField] private string topicInfoRight = "/stereo/right/camera_info";
    [SerializeField] private string topicRobotPose = "/robot/pose";
    [SerializeField] private string topicNameDepth = "/stereo/camera_depth";
    [SerializeField] private string topicRuntimeConfig = "/stereo/config";
    [SerializeField] private string topicConfigReady = "/stereo/config_ready";
    [SerializeField] private string topicConfigReadyAck = "/stereo/config_ready_ack";
    [SerializeField] private string topicConfigAck = "/stereo/config_ack";

    [Header("Image Settings")]
    [SerializeField] private int width = 1080;
    [SerializeField] private int height = 720;
    [SerializeField, Range(1, 100)] private int jpegQuality = 85;
   

    private float baseline;

    [Header("UI Preview")]
    public RawImage vieportCAM1;
    public RawImage vieportCAM2;

    private RenderTexture renderTextureCam1;
    private RenderTexture renderTextureCam2;
    private Texture2D textureCAM1;
    private Texture2D textureCAM2;

    private Camera gtDepthCamera;
    private bool gtDepthPublishingEnabled;
    private RenderTexture depthRT;
    private RenderTexture depthFloatRT;
    private Texture2D depthTexture;
    private Material depthMaterial;
    private int appliedConfigRevision = -1;
    private bool configReadyAcknowledged;
    private float lastReadyPublishTime;
    private string pendingConfigJson;
    private RuntimeStereoConfig appliedRuntimeConfig;
    private bool startupFixtureSaved;
    [SerializeField, Range(2, 100)] private int startupFixtureFrameTarget = 10;
    private string startupFixtureStagingDirectory;
    private int startupFixtureConfigRevision = -1;
    private readonly List<StartupFixtureFrameIndex> startupFixtureFrames = new List<StartupFixtureFrameIndex>();
    private const string StartupFixtureRelativePath = "VisualSLAM/tests/fixtures/unity_startup";


    private System.Diagnostics.Process rosTcpEndpointProcess;
    private System.Diagnostics.Process stereoProcessorNodeProcess;

    void OnApplicationQuit() {
        if (ShellManager.Instance != null){
            ShellManager.Instance.CloseAllProcesses();
        }
    }

    void Start()
    {
        logger = new Logger(GetType().Name);
        if (cam1 == null || cam2 == null) {
            logger.Warn(AppLabels.CAMERA_NOT_ASSIGNED);
            return;
        }

        ros = ROSConnection.GetOrCreateInstance();
        
        ros.RegisterPublisher<ImageMsg>(topicNameLeft);
        ros.RegisterPublisher<ImageMsg>(topicNameRight);
        ros.RegisterPublisher<ImageMsg>(topicNameDepth);
        ros.RegisterPublisher<CameraInfoMsg>(topicInfoLeft);
        ros.RegisterPublisher<CameraInfoMsg>(topicInfoRight);
        ros.RegisterPublisher<PoseStampedMsg>(topicRobotPose);
        ros.RegisterPublisher<StringMsg>(topicConfigReady);
        ros.RegisterPublisher<StringMsg>(topicConfigAck);
        ros.Subscribe<StringMsg>(topicRuntimeConfig, OnRuntimeConfigMessage);
        ros.Subscribe<StringMsg>(topicConfigReadyAck, OnConfigReadyAcknowledged);

        SetupGTDepthCamera();
        RecreateFrameResources();

        if (vieportCAM1 != null) vieportCAM1.texture = textureCAM1;
        if (vieportCAM2 != null) vieportCAM2.texture = textureCAM2;

        cam1.enabled = false;
        cam2.enabled = false;
        baseline = Vector3.Distance(cam1.transform.position, cam2.transform.position);
        logger.Log(string.Format(AppLabels.BASELINE_CALCULATED, baseline));

        if (string.IsNullOrEmpty(Config.Instance.RunRosTcpEndpointSh) || string.IsNullOrEmpty(Config.Instance.RunStereoProcessorNodeSh)) {
            logger.Error(AppLabels.MISSING_ROS_SCRIPTS_PATH);
            return;
        }
        
        rosTcpEndpointProcess = ShellManager.Instance.Execute(Config.Instance.RunRosTcpEndpointSh);
        stereoProcessorNodeProcess = ShellManager.Instance.Execute(Config.Instance.RunStereoProcessorNodeSh);
        
    }

    void Update() {
        ApplyPendingConfiguration();
        PublishConfigurationReady();
        if (ros == null || cam1 == null || cam2 == null) return;
        TimeMsg sharedTimestamp = GetCurrentROSTime();
        SendStereoVisionFrames(sharedTimestamp, out byte[] leftBytes, out byte[] rightBytes);
        bool captureStartupFixture = appliedRuntimeConfig != null && !startupFixtureSaved;
        float[] depthData = RenderDepthFrame(sharedTimestamp, captureStartupFixture);
        CameraCalibration leftCalibration = PublishCameraInfoAndRobotPose(sharedTimestamp, out CameraCalibration rightCalibration);
        if (captureStartupFixture && leftBytes != null && rightBytes != null
                && depthData != null && leftCalibration != null) {
            TrySaveStartupFixture(sharedTimestamp, leftBytes, rightBytes, depthData, leftCalibration, rightCalibration);
        }
    }

    [Serializable]
    private class RuntimeStereoConfig {
        public float min_depth;
        public float max_depth;
        public int width;
        public int height;
        public float baseline;
        public int min_disp;
        public int num_disp_multiplier;
        public int block_size;
        public float wls_lambda;
        public float wls_sigma;
        public bool gt_enabled;
        public int revision;
    }

    [Serializable]
    private class FixtureTimestamp {
        public int sec;
        public int nanosec;
    }

    [Serializable]
    private class CameraCalibration {
        public int width;
        public int height;
        public string distortion_model;
        public double[] d;
        public double[] k;
        public double[] r;
        public double[] p;
        public FixtureTimestamp stamp;
        public string frame_id;
    }

    [Serializable]
    private class StartupFixtureMetadata {
        public int schema_version = 1;
        public string frame_id;
        public int width;
        public int height;
        public string left_image_encoding = "jpeg";
        public string right_image_encoding = "jpeg";
        public string depth_encoding = "32FC1";
        public string depth_units = "m";
        public string depth_byte_order = "little_endian";
        public string depth_preview_encoding = "gray8_near_white";
        public string depth_preview_row_order = "top_to_bottom";
        public float depth_preview_min_m;
        public float depth_preview_max_m;
        public int jpeg_quality;
        public string unity_version;
        public string platform;
        public FixtureTimestamps timestamps;
        public FixtureCameraInfo camera_info;
        public RuntimeStereoConfig config;
    }

    [Serializable]
    private class StartupFixtureCollectionMetadata {
        public int schema_version = 2;
        public int frame_count;
        public int target_frame_count;
        public int width;
        public int height;
        public string unity_version;
        public string platform;
        public RuntimeStereoConfig config;
        public StartupFixtureFrameIndex[] frames;
    }

    [Serializable]
    private class StartupFixtureFrameIndex {
        public string frame_id;
        public string directory;
        public FixtureTimestamp stamp;
    }

    [Serializable]
    private class FixtureTimestamps {
        public FixtureTimestamp left;
        public FixtureTimestamp right;
        public FixtureTimestamp depth;
    }

    [Serializable]
    private class FixtureCameraInfo {
        public CameraCalibration left;
        public CameraCalibration right;
    }

    void OnRuntimeConfigMessage(StringMsg message) {
        if (message != null && !string.IsNullOrEmpty(message.data)) {
            pendingConfigJson = message.data;
        }
    }

    void OnConfigReadyAcknowledged(StringMsg _message) {
        configReadyAcknowledged = true;
    }

    void PublishConfigurationReady() {
        if (ros == null || configReadyAcknowledged || Time.time - lastReadyPublishTime < 1.0f) return;
        StringMsg readyMessage = new StringMsg { data = "ready" };
        ros.Publish(topicConfigReady, readyMessage);
        lastReadyPublishTime = Time.time;
    }

    void ApplyPendingConfiguration() {
        if (string.IsNullOrEmpty(pendingConfigJson)) return;
        RuntimeStereoConfig config;
        try {
            config = JsonUtility.FromJson<RuntimeStereoConfig>(pendingConfigJson);
        } catch (Exception e) {
            logger.Error("Invalid stereo runtime configuration: " + e.Message);
            pendingConfigJson = null;
            return;
        }
        pendingConfigJson = null;
        if (config == null || config.revision < 0 || config.revision < appliedConfigRevision
                || config.width < 16 || config.width > 4096
                || config.height < 16 || config.height > 2160
                || config.min_depth <= 0.0f || config.max_depth <= config.min_depth
                || config.baseline <= 0.0f || float.IsNaN(config.min_depth) || float.IsInfinity(config.min_depth)
                || float.IsNaN(config.max_depth) || float.IsInfinity(config.max_depth)
                || float.IsNaN(config.baseline) || float.IsInfinity(config.baseline)
                || cam1 == null || cam2 == null) return;

        if (config.revision != appliedConfigRevision) {
            if (!startupFixtureSaved && startupFixtureConfigRevision >= 0
                    && startupFixtureConfigRevision != config.revision) {
                ResetStartupFixtureCapture();
            }
            bool dimensionsChanged = width != config.width || height != config.height;
            width = config.width;
            height = config.height;
            baseline = config.baseline;
            gtDepthPublishingEnabled = config.gt_enabled;
            Config.Instance.camera_near = config.min_depth;
            Config.Instance.depth_far = config.max_depth;
            ApplyCameraBaseline(baseline);
            if (gtDepthCamera != null) {
                gtDepthCamera.nearClipPlane = config.min_depth;
                gtDepthCamera.farClipPlane = config.max_depth;
                gtDepthCamera.aspect = (float)width / height;
            }
            if (dimensionsChanged) RecreateFrameResources();
            appliedRuntimeConfig = config;
            appliedConfigRevision = config.revision;
        }
        SendConfigurationAck(config.revision);
    }

    void SendConfigurationAck(int revision) {
        if (ros == null) return;
        StringMsg ack = new StringMsg { data = "{\"revision\":" + revision + "}" };
        ros.Publish(topicConfigAck, ack);
    }

    void ApplyCameraBaseline(float requestedBaseline) {
        Vector3 center = (cam1.transform.position + cam2.transform.position) * 0.5f;
        Vector3 axis = cam2.transform.position - cam1.transform.position;
        if (axis.sqrMagnitude < 0.000001f) axis = cam1.transform.right;
        axis.Normalize();
        cam1.transform.position = center - axis * (requestedBaseline * 0.5f);
        cam2.transform.position = center + axis * (requestedBaseline * 0.5f);
    }

    void RecreateFrameResources() {
        ReleaseTexture(ref renderTextureCam1);
        ReleaseTexture(ref renderTextureCam2);
        ReleaseTexture(ref textureCAM1);
        ReleaseTexture(ref textureCAM2);
        ReleaseTexture(ref depthRT);
        ReleaseTexture(ref depthFloatRT);
        ReleaseTexture(ref depthTexture);

        renderTextureCam1 = new RenderTexture(width, height, 24);
        renderTextureCam2 = new RenderTexture(width, height, 24);
        textureCAM1 = new Texture2D(width, height, TextureFormat.RGB24, false);
        textureCAM2 = new Texture2D(width, height, TextureFormat.RGB24, false);
        if (gtDepthCamera != null) {
            depthRT = new RenderTexture(width, height, 24, RenderTextureFormat.Depth);
            depthFloatRT = new RenderTexture(width, height, 0, RenderTextureFormat.RFloat);
            depthTexture = new Texture2D(width, height, TextureFormat.RFloat, false);
            gtDepthCamera.aspect = (float)width / height;
        }
        ConfigureCamera(cam1, renderTextureCam1);
        ConfigureCamera(cam2, renderTextureCam2);
        if (vieportCAM1 != null) vieportCAM1.texture = textureCAM1;
        if (vieportCAM2 != null) vieportCAM2.texture = textureCAM2;
    }

    void ReleaseTexture<T>(ref T resource) where T : UnityEngine.Object {
        if (resource == null) return;
        if (resource is RenderTexture renderTexture) renderTexture.Release();
        Destroy(resource);
        resource = null;
    }

    void SendStereoVisionFrames(TimeMsg timestamp, out byte[] cam1Bytes, out byte[] cam2Bytes) {
        cam1Bytes = GetCameraFrame(cam1, renderTextureCam1, ref textureCAM1);
        cam2Bytes = GetCameraFrame(cam2, renderTextureCam2, ref textureCAM2);

        PublishImage(topicNameLeft, cam1Bytes, "camera_left_optical_frame", timestamp);
        PublishImage(topicNameRight, cam2Bytes, "camera_right_optical_frame", timestamp);
    }

    byte[] GetCameraFrame(Camera cam, RenderTexture rt, ref Texture2D texture) {
        if (cam == null || rt == null || texture == null) return null;
        cam.targetTexture = rt;
        cam.Render();
        RenderTexture.active = rt;
        texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        texture.Apply();

        byte[] imageBytes = texture.EncodeToJPG(jpegQuality);

        cam.targetTexture = null;
        RenderTexture.active = null;
        return imageBytes;
    }

    void PublishImage(string topic, byte[] imageBytes, string frameId, TimeMsg timestamp) {
        if (imageBytes == null || imageBytes.Length == 0) return;
        HeaderMsg header = new HeaderMsg {
            stamp = timestamp,
            frame_id = frameId
        };

        ImageMsg imgMessage = new ImageMsg {
            header = header,
            height = (uint)height,
            width = (uint)width,
            encoding = "jpeg",
            is_bigendian = 0,
            step = (uint)(width * 3),
            data = imageBytes
        };

        ros.Publish(topic, imgMessage);
    }

    void SetupGTDepthCamera() {
        if (cam1 == null) return;

        GameObject go = new GameObject("GTDepthCamera");
        go.transform.SetParent(cam1.transform, false);
        go.transform.localPosition = Vector3.zero;
        go.transform.localRotation = Quaternion.identity;

        gtDepthCamera = go.AddComponent<Camera>();
        gtDepthCamera.enabled = false;
        gtDepthCamera.fieldOfView = cam1.fieldOfView;
        gtDepthCamera.aspect = (float)width / height;
        gtDepthCamera.cullingMask = cam1.cullingMask;
        gtDepthCamera.nearClipPlane = Config.Instance.CameraNear;
        gtDepthCamera.farClipPlane = Config.Instance.DepthFar;
        gtDepthCamera.depthTextureMode = DepthTextureMode.Depth;

        Shader depthShader = Shader.Find("Hidden/DepthToLinearEye");
        if (depthShader != null) {
            depthMaterial = new Material(depthShader);
        } else {
            logger.Error(AppLabels.DEPTH_SHADER_NOT_FOUND);
        }

        depthRT = new RenderTexture(width, height, 24, RenderTextureFormat.Depth);
        depthFloatRT = new RenderTexture(width, height, 0, RenderTextureFormat.RFloat);
        depthTexture = new Texture2D(width, height, TextureFormat.RFloat, false);

        logger.Log(string.Format(AppLabels.DEPTH_PUBLISHER_STARTED, topicNameDepth));
        logger.Log(string.Format(AppLabels.DEPTH_CLIP_APPLIED, Config.Instance.CameraNear, Config.Instance.DepthFar));
    }

    float[] RenderDepthFrame(TimeMsg timestamp, bool captureForStartupFixture) {
        if ((!gtDepthPublishingEnabled && !captureForStartupFixture) || gtDepthCamera == null || depthRT == null
                || depthFloatRT == null || depthMaterial == null) return null;

        gtDepthCamera.targetTexture = depthRT;
        gtDepthCamera.Render();
        gtDepthCamera.targetTexture = null;
        RenderTexture.active = null;

        ApplyDepthLinearizationParameters();
        Graphics.Blit(depthRT, depthFloatRT, depthMaterial);
        RenderTexture.active = depthFloatRT;
        depthTexture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        depthTexture.Apply();
        RenderTexture.active = null;

        float[] depthData = depthTexture.GetRawTextureData<float>().ToArray();
        if (gtDepthPublishingEnabled) PublishDepthFrame(timestamp, depthData);
        return depthData;
    }

    void ApplyDepthLinearizationParameters() {
        if (depthMaterial == null || gtDepthCamera == null) return;
        float near = gtDepthCamera.nearClipPlane;
        float far = gtDepthCamera.farClipPlane;
        if (near <= 0.0f || far <= near) return;
        if (SystemInfo.usesReversedZBuffer) {
            float x = -1.0f + far / near;
            depthMaterial.SetVector("_DepthZParams", new Vector4(x, 1.0f, x / far, 1.0f / far));
        } else {
            float x = 1.0f - far / near;
            depthMaterial.SetVector("_DepthZParams", new Vector4(x, far / near, x / far, far / near / far));
        }
    }

    void PublishDepthFrame(TimeMsg timestamp, float[] depthData) {
        byte[] depthBytes = new byte[depthData.Length * sizeof(float)];
        Buffer.BlockCopy(depthData, 0, depthBytes, 0, depthBytes.Length);

        ImageMsg depthMessage = new ImageMsg {
            header = new HeaderMsg {
                stamp = timestamp,
                frame_id = "camera_left_optical_frame"
            },
            height = (uint)height,
            width = (uint)width,
            encoding = "32FC1",
            is_bigendian = 0,
            step = (uint)(width * 4),
            data = depthBytes
        };

        ros.Publish(topicNameDepth, depthMessage);
    }

    CameraCalibration PublishCameraInfoAndRobotPose(TimeMsg timestamp, out CameraCalibration rightCalibration) {
        rightCalibration = null;
        if (cam1 == null || cam2 == null) return null;
        float fy = (height / 2.0f) / Mathf.Tan(cam1.fieldOfView * 0.5f * Mathf.Deg2Rad);
        float fx = fy;
        float cx = width / 2.0f;
        float cy = height / 2.0f;

        double[] kMatrix = new double[] {
            fx, 0.0, cx,
            0.0, fy, cy,
            0.0, 0.0, 1.0
        };

        CameraCalibration leftCalibration = CreateCameraCalibration(
            "camera_left_optical_frame", timestamp, kMatrix, 0.0f);
        rightCalibration = CreateCameraCalibration(
            "camera_right_optical_frame", timestamp, kMatrix, -fx * baseline);
        PublishCameraInfo(topicInfoLeft, timestamp, leftCalibration);
        PublishCameraInfo(topicInfoRight, timestamp, rightCalibration);

        Vector3 midpoint = (cam1.transform.position + cam2.transform.position) * 0.5f;
        Quaternion midRot = Quaternion.Slerp(cam1.transform.rotation, cam2.transform.rotation, 0.5f);

        PoseStampedMsg robotPoseMsg = new PoseStampedMsg {
            header = new HeaderMsg { stamp = timestamp, frame_id = "map" },
            pose = new PoseMsg {
                position = new PointMsg(midpoint.x, midpoint.y, midpoint.z),
                orientation = new QuaternionMsg(midRot.x, midRot.y, midRot.z, midRot.w)
            }
        };
        ros.Publish(topicRobotPose, robotPoseMsg);
        return leftCalibration;
    }

    CameraCalibration CreateCameraCalibration(string frameId, TimeMsg time, double[] kMatrix, float tx) {
        double[] pMatrix = new double[] {
            kMatrix[0], kMatrix[1], kMatrix[2], tx,
            kMatrix[3], kMatrix[4], kMatrix[5], 0.0,
            kMatrix[6], kMatrix[7], kMatrix[8], 0.0
        };

        return new CameraCalibration {
            height = height,
            width = width,
            distortion_model = "plumb_bob",
            d = new double[] { 0, 0, 0, 0, 0 },
            k = kMatrix,
            r = new double[] { 1, 0, 0, 0, 1, 0, 0, 0, 1 },
            p = pMatrix,
            stamp = ToFixtureTimestamp(time),
            frame_id = frameId
        };
    }

    void PublishCameraInfo(string topic, TimeMsg time, CameraCalibration calibration) {
        CameraInfoMsg info = new CameraInfoMsg {
            header = new HeaderMsg { stamp = time, frame_id = calibration.frame_id },
            height = (uint)calibration.height,
            width = (uint)calibration.width,
            distortion_model = calibration.distortion_model,
            D = calibration.d,
            K = calibration.k,
            R = calibration.r,
            P = calibration.p
        };
        ros.Publish(topic, info);
    }

    void TrySaveStartupFixture(TimeMsg timestamp, byte[] leftBytes, byte[] rightBytes,
            float[] depthData, CameraCalibration leftCalibration, CameraCalibration rightCalibration) {
        if (leftBytes == null || rightBytes == null || depthData == null
                || leftBytes.Length == 0 || rightBytes.Length == 0 || depthData.Length != width * height
                || leftCalibration == null || rightCalibration == null || appliedRuntimeConfig == null) return;

        string fixtureDirectory = FileManager.GetFullPath(StartupFixtureRelativePath);
        string parentDirectory = Path.GetDirectoryName(fixtureDirectory);
        if (startupFixtureConfigRevision >= 0 && startupFixtureConfigRevision != appliedRuntimeConfig.revision) {
            ResetStartupFixtureCapture();
        }
        if (string.IsNullOrEmpty(startupFixtureStagingDirectory)) {
            startupFixtureStagingDirectory = fixtureDirectory + ".tmp-" + Guid.NewGuid().ToString("N");
            startupFixtureConfigRevision = appliedRuntimeConfig.revision;
            startupFixtureFrames.Clear();
        }
        string backupDirectory = fixtureDirectory + ".old-" + Guid.NewGuid().ToString("N");
        try {
            Directory.CreateDirectory(parentDirectory);
            Directory.CreateDirectory(startupFixtureStagingDirectory);
            string frameId = "frame_" + (startupFixtureFrames.Count + 1).ToString("D6");
            string relativeFrameDirectory = Path.Combine("frames", frameId);
            string frameDirectory = Path.Combine(startupFixtureStagingDirectory, relativeFrameDirectory);
            Directory.CreateDirectory(frameDirectory);
            File.WriteAllBytes(Path.Combine(frameDirectory, "left.jpg"), leftBytes);
            File.WriteAllBytes(Path.Combine(frameDirectory, "right.jpg"), rightBytes);
            byte[] depthBytes = DepthBytesLittleEndian(depthData);
            File.WriteAllBytes(Path.Combine(frameDirectory, "depth_gt_f32le.bin"), depthBytes);
            File.WriteAllBytes(Path.Combine(frameDirectory, "depth_gt.png"),
                EncodeDepthPreviewPng(depthData, appliedRuntimeConfig.min_depth, appliedRuntimeConfig.max_depth));

            StartupFixtureMetadata metadata = new StartupFixtureMetadata {
                frame_id = frameId,
                width = width,
                height = height,
                depth_preview_min_m = appliedRuntimeConfig.min_depth,
                depth_preview_max_m = appliedRuntimeConfig.max_depth,
                jpeg_quality = jpegQuality,
                unity_version = Application.unityVersion,
                platform = Application.platform.ToString(),
                timestamps = new FixtureTimestamps {
                    left = ToFixtureTimestamp(timestamp),
                    right = ToFixtureTimestamp(timestamp),
                    depth = ToFixtureTimestamp(timestamp)
                },
                camera_info = new FixtureCameraInfo {
                    left = leftCalibration,
                    right = rightCalibration
                },
                config = appliedRuntimeConfig
            };
            File.WriteAllText(Path.Combine(frameDirectory, "metadata.json"),
                JsonUtility.ToJson(metadata, true), System.Text.Encoding.UTF8);
            startupFixtureFrames.Add(new StartupFixtureFrameIndex {
                frame_id = frameId,
                directory = relativeFrameDirectory.Replace('\\', '/'),
                stamp = ToFixtureTimestamp(timestamp)
            });

            int targetCount = Mathf.Max(2, startupFixtureFrameTarget);
            if (startupFixtureFrames.Count < targetCount) {
                logger.Log("Captured Unity startup fixture frame " + startupFixtureFrames.Count + "/" + targetCount);
                return;
            }

            StartupFixtureCollectionMetadata collection = new StartupFixtureCollectionMetadata {
                frame_count = startupFixtureFrames.Count,
                target_frame_count = targetCount,
                width = width,
                height = height,
                unity_version = Application.unityVersion,
                platform = Application.platform.ToString(),
                config = appliedRuntimeConfig,
                frames = startupFixtureFrames.ToArray()
            };
            File.WriteAllText(Path.Combine(startupFixtureStagingDirectory, "metadata.json"),
                JsonUtility.ToJson(collection, true), System.Text.Encoding.UTF8);
            if (Directory.Exists(fixtureDirectory)) Directory.Move(fixtureDirectory, backupDirectory);
            try {
                Directory.Move(startupFixtureStagingDirectory, fixtureDirectory);
            } catch {
                if (Directory.Exists(backupDirectory) && !Directory.Exists(fixtureDirectory)) {
                    Directory.Move(backupDirectory, fixtureDirectory);
                }
                throw;
            }
            startupFixtureSaved = true;
            startupFixtureStagingDirectory = null;
            if (Directory.Exists(backupDirectory)) {
                try { Directory.Delete(backupDirectory, true); }
                catch (Exception cleanupError) {
                    Debug.LogWarning("Could not remove previous Unity fixture backup: " + cleanupError.Message);
                }
            }
            logger.Log("Saved " + startupFixtureFrames.Count
                + " synchronized Unity stereo/GT frames to " + fixtureDirectory);
        } catch (Exception error) {
            logger.Error("Could not save Unity startup fixture frame; capture will retry: " + error);
            ResetStartupFixtureCapture();
        }
    }

    void ResetStartupFixtureCapture() {
        if (!string.IsNullOrEmpty(startupFixtureStagingDirectory)
                && Directory.Exists(startupFixtureStagingDirectory)) {
            try { Directory.Delete(startupFixtureStagingDirectory, true); }
            catch (Exception cleanupError) {
                Debug.LogWarning("Could not remove incomplete Unity fixture capture: " + cleanupError.Message);
            }
        }
        startupFixtureStagingDirectory = null;
        startupFixtureConfigRevision = -1;
        startupFixtureFrames.Clear();
    }

    byte[] DepthBytesLittleEndian(float[] depthData) {
        byte[] bytes = new byte[depthData.Length * sizeof(float)];
        Buffer.BlockCopy(depthData, 0, bytes, 0, bytes.Length);
        if (!BitConverter.IsLittleEndian) {
            for (int i = 0; i < bytes.Length; i += sizeof(float)) {
                Array.Reverse(bytes, i, sizeof(float));
            }
        }
        return bytes;
    }

    byte[] EncodeDepthPreviewPng(float[] depthData, float minDepth, float maxDepth) {
        Texture2D preview = new Texture2D(width, height, TextureFormat.RGB24, false);
        try {
            Color32[] pixels = new Color32[depthData.Length];
            float depthRange = maxDepth - minDepth;
            for (int y = 0; y < height; y++) {
                // Texture2D pixel rows use a bottom origin; EncodeToPNG writes
                // top-to-bottom rows, so this maps the raw depth row order once.
                int sourceRow = (height - 1 - y) * width;
                int targetRow = y * width;
                for (int x = 0; x < width; x++) {
                    float depth = depthData[sourceRow + x];
                    byte gray = 0;
                    if (depth > 0.0f && !float.IsNaN(depth) && !float.IsInfinity(depth)) {
                        float normalized = Mathf.Clamp01((maxDepth - depth) / depthRange);
                        gray = (byte)Mathf.RoundToInt(normalized * 255.0f);
                    }
                    pixels[targetRow + x] = new Color32(gray, gray, gray, 255);
                }
            }
            preview.SetPixels32(pixels);
            preview.Apply();
            return preview.EncodeToPNG();
        } finally {
            Destroy(preview);
        }
    }

    FixtureTimestamp ToFixtureTimestamp(TimeMsg timestamp) {
        return new FixtureTimestamp { sec = timestamp.sec, nanosec = (int)timestamp.nanosec };
    }

    TimeMsg GetCurrentROSTime() {
        double time = Time.timeAsDouble;
        int seconds = (int)System.Math.Floor(time);
        uint nanoseconds = (uint)((time - seconds) * 1_000_000_000.0);
        return new TimeMsg(seconds, nanoseconds);
    }

    void ConfigureCamera(Camera cam, RenderTexture rt) {
        if (cam != null) {
            cam.aspect = (float)width / height;
            cam.targetTexture = rt;
        }
    }

    void OnDestroy() {
        ReleaseTexture(ref renderTextureCam1);
        ReleaseTexture(ref renderTextureCam2);
        ReleaseTexture(ref textureCAM1);
        ReleaseTexture(ref textureCAM2);
        ReleaseTexture(ref depthRT);
        ReleaseTexture(ref depthFloatRT);
        ReleaseTexture(ref depthTexture);
        if (depthMaterial != null) Destroy(depthMaterial);
        if (gtDepthCamera != null) Destroy(gtDepthCamera.gameObject);
    }
}
