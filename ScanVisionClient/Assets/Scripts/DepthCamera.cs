using UnityEngine;
using UnityEngine.UI;
using System.IO;

[RequireComponent(typeof(Camera))]
public class DepthCamera: MonoBehaviour
{
    private Camera depthCamera;                
    public RawImage viewport;
    private Texture2D depthMap;

    private RenderTexture depthMapRT;
    public bool saveToFile = false;
    private int width = 0;
    private int height = 0;
    void Start()
    {
        width = (int)viewport.rectTransform.rect.width;
        height = (int)viewport.rectTransform.rect.height;
        depthCamera = GetComponent<Camera>();
        depthCamera.targetTexture = new RenderTexture(width, height, 24, RenderTextureFormat.Depth);
        depthCamera.depthTextureMode = DepthTextureMode.Depth;

        depthMapRT = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
        depthMap = new Texture2D(width, height, TextureFormat.RFloat, false);
    }

    void Update() => RenderDepthMap();

    void RenderDepthMap(){
        Graphics.Blit(depthCamera.targetTexture , depthMapRT);

        RenderTexture.active = depthMapRT;
        depthMap.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        depthMap.Apply();

        viewport.texture = depthMap;
        if(saveToFile && Time.frameCount % 60 == 0) SaveToFile();

        RenderTexture.active = null;
    }

    void SaveToFile(){
        byte[] bytes = depthMap.EncodeToPNG();
        string filePath = "DepthMap.png";
        File.WriteAllBytes(filePath, bytes);
    }

        
}
