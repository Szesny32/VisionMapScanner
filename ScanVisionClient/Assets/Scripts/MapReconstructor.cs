using UnityEngine;
using System.IO;
using System.Collections.Generic;

public class MapReconstructor : MonoBehaviour
{
    public VoxelRender voxelRender;
    private string filePath = "DepthMap.png";
    private Texture2D heightMap;
    private int rWidth = 10, rHeight = 10, rDepth = 50;
    int width, height;
    float xScale, yScale, zScale;

    void OnEnable(){
        byte[] fileData = File.ReadAllBytes(filePath);
        heightMap = new Texture2D(2, 2);
        heightMap.LoadImage(fileData);

        width = heightMap.width;
        height = heightMap.height;

        xScale = rWidth / (float)width;
        yScale = rHeight / (float)height;
        zScale = rDepth;
    }

     void Start() {
        Camera.main.clearFlags = CameraClearFlags.SolidColor; 
        Camera.main.backgroundColor = Color.black;

        (List<Vector3>vertices , List<Color> colors) = GenerateVoxels();
        voxelRender.SetVoxels(vertices.ToArray(), colors.ToArray());
     }

    (List<Vector3>, List<Color>) GenerateVoxels(){
        List<Vector3> vertices = new List<Vector3>();
        List<Color> colors = new List<Color>();
        
        for (int y = 0; y < height; y++){
            for (int x = 0; x < width; x++){
                Color pixel = heightMap.GetPixel(x, y);
                float z = 1f - pixel.grayscale;
                if(z !=1f){
                    vertices.Add(new Vector3(x * xScale , y  * yScale , z * zScale));
                    colors.Add(new Color(pixel.r, 0, 0));
                }
            }
        }
        return (vertices, colors);
    }

}
