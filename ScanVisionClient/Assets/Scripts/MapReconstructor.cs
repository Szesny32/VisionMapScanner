using UnityEngine;
using UnityEngine.UI;
using System.IO;
using System.Collections.Generic;

public class MapReconstructor : MonoBehaviour
{
    public VoxelRender voxelRender;
    public VoxelRender scanVoxelRender;
    public float zScan = 0f;
    
    private string filePath = "DepthMap.png";
    private Texture2D heightMap;
    int width, height;
    public float xScale = 1f, yScale = 1f, zScale =1f;
    public float f;
    float  fx, fy, cx, cy;
    float fov;
    float aspectRatio;

    [Range(0,1)] public float maxDepth = 1f;

    public RawImage viewport;

     public bool voxelsUpdated = false;
    void OnEnable(){
        byte[] fileData = File.ReadAllBytes(filePath);
        heightMap = new Texture2D(2, 2);
        heightMap.LoadImage(fileData);
        viewport.texture = heightMap;

        width = heightMap.width;
        height = heightMap.height;
        aspectRatio =  (float)width / height;



        fov = 60;
        

        float fovY = fov;
        float fovY_rad = Mathf.Deg2Rad * fovY;
        float fovX_rad = 2f * Mathf.Atan(aspectRatio * Mathf.Tan(fovY_rad / 2f));

        fx = width / (2f * Mathf.Tan(fovX_rad * 0.5f));
        fy = height / (2f * Mathf.Tan(fovY_rad * 0.5f));


        cx = width/2f; 
        cy = height/2f; 

        

        DebugCamParam();

    }

    void DebugCamParam(){
        string log = $"FOV: {fov}\n";
        log += $"resolution: {width}px x {height}px\n";
        log += $"aspectRatio: {aspectRatio}\n";
        log += $"f: {f}\n";
        log += $"fx: {fx}\n";
        log += $"fy: {fy}\n";
        log += $"cx: {cx}\n";
        log += $"cy: {cy}\n";
        Debug.Log(log);
    }

     void Start() {
        Camera.main.clearFlags = CameraClearFlags.SolidColor; 
        Camera.main.backgroundColor = Color.black;

        (List<Vector3>vertices , List<Color> colors) = GenerateVoxels();
        voxelRender.SetVoxels(vertices.ToArray(), colors.ToArray(), 0.05f);
     }
     void Update(){
        Debug.DrawRay(transform.position, Vector3.forward, Color.red);

        if(voxelsUpdated){
            (List<Vector3>vertices , List<Color> colors) = GenerateVoxels();
            voxelRender.SetVoxels(vertices.ToArray(), colors.ToArray(), 0.05f);
            voxelsUpdated = false;
        }

       //if(Time.frameCount % 2 == 0)
        scan();
     }


    (List<Vector3>, List<Color>) GenerateVoxels(){
        List<Vector3> vertices = new List<Vector3>();
        List<Color> colors = new List<Color>();

        vertices.Add(new Vector3(-5  , 0  , 0));
        colors.Add(new Color(0, 0, 1));
        vertices.Add(new Vector3(5  , 0  , 0));
        colors.Add(new Color(0, 0, 1));
        // for (float z = 0; z <= 1.0f; z+=0.01f){

        //     float depth = LinearDepth(z, 0.3f, 1000f);
        //     (float x, float y) = toOrthogonal(0, 0, depth);
        //     vertices.Add(new Vector3( x , y  , depth));
        //     colors.Add(new Color(0, 1, 0));

        //     (x,  y) = toOrthogonal(0, height-1, depth);
        //     vertices.Add(new Vector3( x , y  , depth));
        //     colors.Add(new Color(0, 1, 0));

        //     (x,  y) = toOrthogonal(width-1, height-1, depth);
        //     vertices.Add(new Vector3( x , y  , depth));
        //     colors.Add(new Color(0, 1, 0));



        //     (x,  y) = toOrthogonal(width-1, 0, depth);
        //     vertices.Add(new Vector3( x , y  , depth));
        //     colors.Add(new Color(0, 1, 0));

        // }

        // int dy = height / 10;
        // int dx = width / 10;

        // for (int y = 0; y < height; y+=dy){
        //     for (int x = 0; x < width; x+=dx){
        //         float depth = LinearDepth(0.5f, 0.3f, 1000f);
        //         (float oX, float oY) = toOrthogonal(x, y, depth);
        //         vertices.Add(new Vector3( oX, oY, depth));
        //         colors.Add(new Color(0, 1, 0));
        //     }
        // }

        // for (int y = 0; y < height; y+=dy){
        //     for (int x = 0; x < width; x+=dx){
        //         float depth = LinearDepth(0.75f, 0.3f, 1000f);
        //         (float oX, float oY) = toOrthogonal(x, y, depth);
        //         vertices.Add(new Vector3( oX, oY, depth));
        //         colors.Add(new Color(0, 1, 0));
        //     }
        // }

        for (int y = 0; y < height; y++){
            for (int x = 0; x < width; x++){
                Color pixel = heightMap.GetPixel(x, y);
                float depthNDC = 1f - pixel.grayscale;
                if(depthNDC <=maxDepth){
                    float z = LinearDepth(depthNDC, 0.3f, 1000f);
                    (float oX, float oY) = toOrthogonal(x, y, z);
                    vertices.Add(new Vector3(oX * xScale  , oY * yScale  , z * zScale));
                    colors.Add(new Color(pixel.r, 0, 0));

                }
            }
        }
        return (vertices, colors);
    }

    float LinearDepth(float depth, float near, float far)
    {
        return (near * far) / (far - depth * (far - near));
    }

    (float, float) toOrthogonal(float u, float v, float Z){

        float X = (float)(u - cx) * (Z/ fx);
        float Y = (float)(v - cy) * (Z / fy);
        return (X, Y);
    }

    void scan(){
        List<Vector3> vertices = new List<Vector3>();
        List<Color> colors = new List<Color>();
  
        int dy = height / 10;
        int dx = width / 10;

        for (int y = 0; y < height; y+=dy){
            for (int x = 0; x < width; x+=dx){
                float depth = LinearDepth(zScan, 0.3f, 1000f);
                (float oX, float oY) = toOrthogonal(x, y, depth);
                vertices.Add(new Vector3( oX, oY, depth));
                colors.Add(new Color(0, 1, 0));
            }
        }

        scanVoxelRender.SetVoxels(vertices.ToArray(), colors.ToArray(), 0.02f);
        zScan = (zScan +0.01f)%maxDepth;
    }



    

}
