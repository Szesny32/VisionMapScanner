using UnityEngine;
using UnityEngine.UI;
using System;
using System.Net.Sockets;

public class StereovisionCapture : MonoBehaviour {
    private UdpClient udpClient;
    public Camera cam1;        
    public Camera cam2;
    [SerializeField] private string host = "127.0.0.1";
    [SerializeField] private int port = 12345;
    [SerializeField] private int width = 1080;
    [SerializeField] private int height = 720;
    RenderTexture renderTexture;
    Texture2D textureCAM1;
    Texture2D textureCAM2;

    public RawImage vieportCAM1;
    public RawImage vieportCAM2;



    void Start() {
        udpClient = new UdpClient();
        renderTexture = new RenderTexture(width, height, 24);
        textureCAM1 = new Texture2D(width, height, TextureFormat.RGB24, false);
        textureCAM2 = new Texture2D(width, height, TextureFormat.RGB24, false);

        vieportCAM1.texture = textureCAM1;
        vieportCAM2.texture = textureCAM2;
        
        ForceCameraResolution(cam1);
        ForceCameraResolution(cam2);

        cam1.enabled = false;
        cam2.enabled = false;

        
        Camera cam = cam1;
        Matrix4x4 projectionMatrix = cam.projectionMatrix;

        // Parametry kamery
        float fov = cam.fieldOfView;  // Kąt widzenia kamery
        float aspect = cam.aspect;    // Proporcja szerokości do wysokości
        float near = cam.nearClipPlane;  // Płaszczyzna "near"
        float far = cam.farClipPlane;    // Płaszczyzna "far"

        // Debugowanie wartości FOV, aspektu, near i far
        Debug.Log("FOV: " + fov);
        Debug.Log("Aspect: " + aspect);
        Debug.Log("Near Clipping Plane: " + near);
        Debug.Log("Far Clipping Plane: " + far);

        // Obliczanie wartości ogniskowych (f_x, f_y)
        float f_x = 1.0f / Mathf.Tan(Mathf.Deg2Rad * (fov * 0.5f));
        float f_y = f_x * aspect;

        // Debugowanie ogniskowych
        Debug.Log("f_x: " + f_x);
        Debug.Log("f_y: " + f_y);

        // Sprawdzenie elementów macierzy
        Debug.Log("Projection Matrix:");
        Debug.Log(projectionMatrix);

        // Obliczenia dla macierzy
        Debug.Log("M00 (1/f_x): " + projectionMatrix.m00);  // Sprawdzanie m00
        Debug.Log("M11 (1/f_y): " + projectionMatrix.m11);  // Sprawdzanie m11
        Debug.Log("M22 (z_far / (z_far - z_near)): " + projectionMatrix.m22);  // Sprawdzanie m22
        Debug.Log("M23 (-z_near * z_far / (z_far - z_near)): " + projectionMatrix.m23);  // Sprawdzanie m23
    
    }

    void OnApplicationQuit() => udpClient.Close();
    void Update() => SendStereoVisionFrames();
    
    void SendStereoVisionFrames() {
        byte[] cam1ImageBytes = GetCameraFrame(cam1, ref textureCAM1);
        byte[] cam2ImageBytes = GetCameraFrame(cam2, ref textureCAM2);
        byte[] combinedPacket = CombineImages(cam1ImageBytes, cam2ImageBytes);
        udpClient.Send(combinedPacket, combinedPacket.Length, host, port);
    }

    byte[] GetCameraFrame(Camera cam, ref Texture2D texture) {
        cam.targetTexture = renderTexture;
        cam.Render();
        RenderTexture.active = renderTexture;
        texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        texture.Apply();

        byte[] imageBytes = texture.EncodeToJPG();

        cam.targetTexture = null;
        RenderTexture.active = null;
        return imageBytes;
    }

    byte[] CombineImages(byte[] cam1ImageBytes, byte[] cam2ImageBytes) {
        byte[] combined = new byte[8 + cam1ImageBytes.Length + cam2ImageBytes.Length];
        Buffer.BlockCopy(BitConverter.GetBytes(cam1ImageBytes.Length), 0, combined, 0, 4);
        Buffer.BlockCopy(BitConverter.GetBytes(cam2ImageBytes.Length), 0, combined, 4, 4);
        Buffer.BlockCopy(cam1ImageBytes, 0, combined, 8, cam1ImageBytes.Length);
        Buffer.BlockCopy(cam2ImageBytes, 0, combined, 8 + cam1ImageBytes.Length, cam2ImageBytes.Length);
        return combined;
    }

    void ForceCameraResolution(Camera cam) {
        if (cam != null) {
            cam.aspect = (float)width / height;
            cam.targetTexture = new RenderTexture(width, height, 24);
        }
    }

}