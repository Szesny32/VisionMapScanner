using System.Net.Sockets;
using UnityEngine;

public class StereovisionCapture : MonoBehaviour {
    private UdpClient udpClient;
    public Camera cam1;        
    public Camera cam2;
    [SerializeField] private string host = "127.0.0.1";
    [SerializeField] private int port = 12345;
    [SerializeField] private int width = 1080;
    [SerializeField] private int height = 720;
    RenderTexture renderTexture;
    Texture2D texture;

    void Start() {
        udpClient = new UdpClient();
        renderTexture = new RenderTexture(width, height, 24);
        texture = new Texture2D(width, height, TextureFormat.RGB24, false);

        ForceCameraResolution(cam1);
        ForceCameraResolution(cam2);
    }

    void OnApplicationQuit() => udpClient.Close();
    void Update() => SendStereoVisionFrames();
    
    void SendStereoVisionFrames() {
        byte[] cam1ImageBytes = GetCameraFrame(cam1, "CAM1");
        byte[] cam2ImageBytes = GetCameraFrame(cam2, "CAM2");
        byte[] combinedPacket = CombineImages(cam1ImageBytes, cam2ImageBytes);
        udpClient.Send(combinedPacket, combinedPacket.Length, host, port);
    }

    byte[] GetCameraFrame(Camera cam, string camID) {
        cam.targetTexture = renderTexture;
        cam.Render();
        RenderTexture.active = renderTexture;
        texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        texture.Apply();

        byte[] imageBytes = texture.EncodeToJPG();
        byte[] headerBytes = System.Text.Encoding.UTF8.GetBytes(camID + ":");
        byte[] packet = new byte[headerBytes.Length + imageBytes.Length];
        System.Buffer.BlockCopy(headerBytes, 0, packet, 0, headerBytes.Length);
        System.Buffer.BlockCopy(imageBytes, 0, packet, headerBytes.Length, imageBytes.Length);

        cam.targetTexture = null;
        RenderTexture.active = null;
        return packet;
    } 

    byte[] CombineImages(byte[] cam1ImageBytes, byte[] cam2ImageBytes) {
        byte[] combined = new byte[cam1ImageBytes.Length + cam2ImageBytes.Length];
        System.Buffer.BlockCopy(cam1ImageBytes, 0, combined, 0, cam1ImageBytes.Length);
        System.Buffer.BlockCopy(cam2ImageBytes, 0, combined, cam1ImageBytes.Length, cam2ImageBytes.Length);
        return combined;
    }

    void ForceCameraResolution(Camera cam) {
        if (cam != null) {
            cam.aspect = (float)width / height;
            cam.targetTexture = new RenderTexture(width, height, 24);
        }
    }

}