using UnityEngine;
using UnityEngine.UI;
using System;
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
        ros = ROSConnection.GetOrCreateInstance();
        
        ros.RegisterPublisher<ImageMsg>(topicNameLeft);
        ros.RegisterPublisher<ImageMsg>(topicNameRight);
        ros.RegisterPublisher<CameraInfoMsg>(topicInfoLeft);
        ros.RegisterPublisher<CameraInfoMsg>(topicInfoRight);
        ros.RegisterPublisher<PoseStampedMsg>(topicRobotPose);

        renderTextureCam1 = new RenderTexture(width, height, 24);
        renderTextureCam2 = new RenderTexture(width, height, 24);

        textureCAM1 = new Texture2D(width, height, TextureFormat.RGB24, false);
        textureCAM2 = new Texture2D(width, height, TextureFormat.RGB24, false);

        if (vieportCAM1 != null) vieportCAM1.texture = textureCAM1;
        if (vieportCAM2 != null) vieportCAM2.texture = textureCAM2;

        ConfigureCamera(cam1, renderTextureCam1);
        ConfigureCamera(cam2, renderTextureCam2);

        cam1.enabled = false;
        cam2.enabled = false;

        if (cam1 == null || cam2 == null) {
            logger.Warn(AppLabels.CAMERA_NOT_ASSIGNED);
            return;
        } 
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
        TimeMsg sharedTimestamp = GetCurrentROSTime();
        SendStereoVisionFrames(sharedTimestamp);
        PublishCameraInfoAndRobotPose(sharedTimestamp);
    }

    void SendStereoVisionFrames(TimeMsg timestamp) {
        byte[] cam1Bytes = GetCameraFrame(cam1, renderTextureCam1, ref textureCAM1);
        byte[] cam2Bytes = GetCameraFrame(cam2, renderTextureCam2, ref textureCAM2);

        PublishImage(topicNameLeft, cam1Bytes, "camera_left_optical_frame", timestamp);
        PublishImage(topicNameRight, cam2Bytes, "camera_right_optical_frame", timestamp);
    }

    byte[] GetCameraFrame(Camera cam, RenderTexture rt, ref Texture2D texture) {
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

    void PublishCameraInfoAndRobotPose(TimeMsg timestamp) {
        float fy = (height / 2.0f) / Mathf.Tan(cam1.fieldOfView * 0.5f * Mathf.Deg2Rad);
        float fx = fy;
        float cx = width / 2.0f;
        float cy = height / 2.0f;

        double[] kMatrix = new double[] {
            fx, 0.0, cx,
            0.0, fy, cy,
            0.0, 0.0, 1.0
        };

        PublishCameraInfo(topicInfoLeft, "camera_left_optical_frame", timestamp, kMatrix, 0.0f);
        PublishCameraInfo(topicInfoRight, "camera_right_optical_frame", timestamp, kMatrix, -fx * baseline);

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
    }

    void PublishCameraInfo(string topic, string frameId, TimeMsg time, double[] kMatrix, float tx) {
        double[] pMatrix = new double[] {
            kMatrix[0], kMatrix[1], kMatrix[2], tx,
            kMatrix[3], kMatrix[4], kMatrix[5], 0.0,
            kMatrix[6], kMatrix[7], kMatrix[8], 0.0
        };

        CameraInfoMsg info = new CameraInfoMsg {
            header = new HeaderMsg { stamp = time, frame_id = frameId },
            height = (uint)height,
            width = (uint)width,
            distortion_model = "plumb_bob",
            D = new double[] { 0, 0, 0, 0, 0 },
            K = kMatrix,
            R = new double[] { 1, 0, 0, 0, 1, 0, 0, 0, 1 },
            P = pMatrix
        };
        ros.Publish(topic, info);
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
        if (renderTextureCam1 != null) { renderTextureCam1.Release(); Destroy(renderTextureCam1); }
        if (renderTextureCam2 != null) { renderTextureCam2.Release(); Destroy(renderTextureCam2); }
        if (textureCAM1 != null) Destroy(textureCAM1);
        if (textureCAM2 != null) Destroy(textureCAM2);
    }
}