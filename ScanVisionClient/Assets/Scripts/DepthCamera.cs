using UnityEngine;
using UnityEngine.UI;
using System.IO;

public struct CameraCalibration{
    public int width;
    public int height;
    public float f;
    public float  fx, fy, cx, cy;
    public float fov;
    public float aspectRatio;
}

[RequireComponent(typeof(Camera))]
public class DepthCamera: MonoBehaviour
{
    private Camera depthCamera;                
    public RawImage viewport;
    private Texture2D depthMap;

    private Transform cameraTransform;

    private RenderTexture depthMapRT;
    public bool saveToFile = false;


    private CameraCalibration cameraCalibration;

    void Start()
    {
        int width = cameraCalibration.width = (int)viewport.rectTransform.rect.width;
        int height = cameraCalibration.height = (int)viewport.rectTransform.rect.height;
        
        depthCamera = GetComponent<Camera>();
        cameraTransform = depthCamera.transform;
        depthCamera.rect = new Rect(0, 0, width, height);
        depthCamera.targetTexture = new RenderTexture(width, height, 24, RenderTextureFormat.Depth);
        depthCamera.depthTextureMode = DepthTextureMode.Depth;

        depthMapRT = new RenderTexture(width, height, 24, RenderTextureFormat.RFloat);
        depthMap = new Texture2D(width, height, TextureFormat.RFloat, false);

        Calibration();
    }

    //TODO: OnRequest?
    void Update() => RenderDepthMap();

    void RenderDepthMap(){
        Graphics.Blit(depthCamera.targetTexture , depthMapRT);

        RenderTexture.active = depthMapRT;
        depthMap.ReadPixels(new Rect(0, 0, cameraCalibration.width, cameraCalibration.height), 0, 0);
        depthMap.Apply();
        cameraTransform = transform;

        viewport.texture = depthMap;
        if(saveToFile && Time.frameCount % 60 == 0) SaveToFile();

        RenderTexture.active = null;
    }

    void SaveToFile(){
        byte[] bytes = depthMap.EncodeToPNG();
        string filePath = "DepthMap.png";
        File.WriteAllBytes(filePath, bytes);
    }

    public byte[] RetrieveData(ref Transform cameraTransform){
        cameraTransform = this.cameraTransform;
        byte[] data = depthMap.EncodeToPNG();
        return data;
    }

    private void Calibration(){
        int width = cameraCalibration.width;
        int height = cameraCalibration.height;
        cameraCalibration.aspectRatio =  (float)width / height;
        cameraCalibration.fov = 60;
        float fovY = cameraCalibration.fov;
        float fovY_rad = Mathf.Deg2Rad * fovY;
        float fovX_rad = 2f * Mathf.Atan(cameraCalibration.aspectRatio * Mathf.Tan(fovY_rad / 2f));

        cameraCalibration.fx = width / (2f * Mathf.Tan(fovX_rad * 0.5f));
        cameraCalibration.fy = height / (2f * Mathf.Tan(fovY_rad * 0.5f));
        cameraCalibration.cx = width/2f; 
        cameraCalibration.cy = height/2f; 
    }

    private void DisplayCamParams(){
        string log = $"FOV: {cameraCalibration.fov}\n";
        log += $"resolution: {cameraCalibration.width}px x {cameraCalibration.height}px\n";
        log += $"aspectRatio: {cameraCalibration.aspectRatio}\n";
        log += $"fx: {cameraCalibration.fx}\n";
        log += $"fy: {cameraCalibration.fy}\n";
        log += $"cx: {cameraCalibration.cx}\n";
        log += $"cy: {cameraCalibration.cy}\n";
        Debug.Log(log);
    }

    public CameraCalibration GetCalibrationData(){
        return cameraCalibration;
    }

}
