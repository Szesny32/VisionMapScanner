using UnityEngine;
using UnityEngine.UI;
using System.IO;
using System.Collections.Generic;

public class MapReconstructor : MonoBehaviour
{
    public VoxelRender voxelRender;
    public VoxelRender scanVoxelRender;
   
    private Octree octree;
    public float zScan = 0f;
    
    private string defaultDepthMapPath = "DepthMap.png";
    private Texture2D depthMap;
    public float xScale = 1f, yScale = 1f, zScale =1f;


    public DepthCamera depthCam;
    private CameraCalibration cameraCalibration;
    private Transform cameraTransform;



    [Range(0,1)] public float maxDepth = 1f;

    public bool fromDepthCamera = false;

    public RawImage viewport;

    public bool voxelsUpdated = false;


    private Vector3 chunkPosition;
    public int resolution = 8;

    private byte[] RetrieveDepthCameraData(DepthCamera depthCam){
        return depthCam != null? 
            depthCam.RetrieveData(ref cameraTransform) : 
            File.ReadAllBytes(defaultDepthMapPath);
    }
    
    void Start(){
        depthMap = new Texture2D(2, 2);
        chunkPosition = new Vector3(0.5f, 0.5f, 0.5f);
        octree = new Octree(chunkPosition, resolution);
        viewport.texture = depthMap;

        if(depthCam!=null) cameraCalibration = depthCam.GetCalibrationData();
    }

    




    void Update(){
        
        if(depthCam==null) return;
        
        UpdateDepthMap();
        UpdateOctree();

        //TODO: check if updated
        if(Time.frameCount % 10 == 0){
            (List<Vector3>vertices , List<Color> colors, List<float> sizes) = octree.GetColoredLeafPositions();
           // voxelRender.SetVoxels(vertices.ToArray(), colors.ToArray(), sizes.ToArray());
        }

        Debug.DrawRay(new Vector3(0,0,0), Vector3.forward, Color.red);
        Debug.DrawRay(new Vector3(0,0,1),Vector3.right, Color.red);
        Debug.DrawRay(new Vector3(1,0,1), Vector3.back, Color.red);
        Debug.DrawRay(new Vector3(1,0,0), Vector3.left, Color.red);

        Debug.DrawRay(new Vector3(0,1,0), Vector3.forward, Color.red);
        Debug.DrawRay(new Vector3(0,1,1),Vector3.right, Color.red);
        Debug.DrawRay(new Vector3(1,1,1), Vector3.back, Color.red);
        Debug.DrawRay(new Vector3(1,1,0), Vector3.left, Color.red);

        Debug.DrawRay(new Vector3(0,0,0), Vector3.up, Color.red);
        Debug.DrawRay(new Vector3(0,0,1),Vector3.up, Color.red);
        Debug.DrawRay(new Vector3(1,0,1), Vector3.up, Color.red);
        Debug.DrawRay(new Vector3(1,0,0), Vector3.up, Color.red);


    }

    
    private void UpdateDepthMap(){
        byte[] dataBuffer = RetrieveDepthCameraData(depthCam);
        depthMap.LoadImage(dataBuffer);
    }
    private void UpdateOctree(){

        for (int y = 0; y < cameraCalibration.height; y++){
            for (int x = 0; x < cameraCalibration.width; x++){
                Color pixel = depthMap.GetPixel(x, y);
                float depthNDC = 1f - pixel.grayscale;
                if(depthNDC <=maxDepth){
                    float z = LinearDepth(depthNDC, 0.3f, 1000f);
                    (float oX, float oY) = toOrthogonal(x, y, z);
                    
                    Vector3 worldPosition = fromDepthCamera?
                    cameraTransform.position+cameraTransform.rotation * new Vector3(oX * xScale, oY * yScale, z * zScale)
                    : new Vector3(oX * xScale, oY * yScale, z * zScale);
                    octree.Insert(worldPosition);
                }
            }
        }
    }


    float LinearDepth(float depth, float near, float far)
    {
        return (near * far) / (far - depth * (far - near));
    }

    (float, float) toOrthogonal(float u, float v, float Z){

        float X = (float)(u - cameraCalibration.cx) * (Z / cameraCalibration.fx);
        float Y = (float)(v - cameraCalibration.cy) * (Z / cameraCalibration.fy);
        return (X, Y);
    }


    // void scan(){
    //     List<Vector3> vertices = new List<Vector3>();
    //     List<Color> colors = new List<Color>();
  
    //     int dy = height / 10;
    //     int dx = width / 10;

    //     for (int y = 0; y < height; y+=dy){
    //         for (int x = 0; x < width; x+=dx){
    //             float depth = LinearDepth(zScan, 0.3f, 1000f);
    //             (float oX, float oY) = toOrthogonal(x, y, depth);
    //             vertices.Add(new Vector3( oX, oY, depth));
    //             colors.Add(new Color(0, 1, 0));
    //         }
    //     }

    //     scanVoxelRender.SetVoxels(vertices.ToArray(), colors.ToArray(), 0.02f);
    //     zScan = (zScan +0.01f)%maxDepth;
    // }


}
