using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;
public class SceneReconstructor : MonoBehaviour
{
    
    [SerializeField] private GameObject chunkPrefab;
    [SerializeField] private int range = 3;
    private Chunk[,] chunks;


    [SerializeField] private DepthCamera depthCam;
    private CameraCalibration depthCamCalibration;
    private Texture2D depthMap;
    public RawImage viewport;
    private Transform cameraTransform;

    [SerializeField] private Transform sceneAnchor;


    void Start()
    {
        chunks = new Chunk[1 + 2*range, 1 + 2*range];
        for(int x = 0; x < 2*range + 1; x++){
            for(int z = 0; z < 2*range + 1; z++){ 
                Vector3 chunkPosition = new Vector3(x -range+ 0.5f, 0.5f, z-range+0.5f);
                chunks[x, z] = Instantiate(chunkPrefab, this.transform).GetComponent<Chunk>();
                chunks[x, z].Init(chunkPosition, 6);
            }
        }

        if(depthCam==null) return;
        depthCamCalibration = depthCam.GetCalibrationData();
        depthMap = new Texture2D(2, 2);
        viewport.texture = depthMap;


    }


    void Update()
    {
        if(depthCam==null || Time.frameCount % 10 != 0) return;
        UpdateDepthMap();
        HashSet<Chunk> chunksToUpdate = UpdateChunks();
        RefreshChunks(chunksToUpdate);
    }

    private void UpdateDepthMap(){
        byte[] dataBuffer = depthCam.RetrieveData(ref cameraTransform); 
        depthMap.LoadImage(dataBuffer);
    }

    private HashSet<Chunk> UpdateChunks(){
        HashSet<Chunk> chunksToUpdate = new HashSet<Chunk>();
        for (int y = 0; y < depthCamCalibration.height; y++){
            for (int x = 0; x < depthCamCalibration.width; x++){
                Color pixel = depthMap.GetPixel(x, y);
                float depthNDC = 1f - pixel.grayscale;
                if(depthNDC <= 0.99f){
                    float z = LinearDepth(depthNDC, 0.3f, 1000f);
                    (float oX, float oY) = toOrthogonal(x, y, z);
                    
                    Vector3 worldPosition = cameraTransform.position+cameraTransform.rotation * new Vector3(oX, oY , z);
                    Vector3 scenePosition = worldPosition - sceneAnchor.position;
                    Chunk chunk = GetChunk(scenePosition);
                    if(chunk && chunk.UpdateOctree(scenePosition)) {
                        chunksToUpdate.Add(chunk);
                    }
                }
            }
        }
        return chunksToUpdate;
    }

    private void RefreshChunks(HashSet<Chunk> chunks){
        foreach(Chunk chunk in chunks){
            chunk.RefreshVoxels();
        }
    }



   

    private Chunk GetChunk(Vector3 scenePosition ){

        if(scenePosition.x > range +0.5f || scenePosition.x < -range +0.5f) return null;
        if(scenePosition.z > range +0.5f || scenePosition.z < -range +0.5f) return null;

        int x = (int)Mathf.Floor(scenePosition.x + range);
        int z = (int)Mathf.Floor(scenePosition.z + range);

        return chunks[x, z];
    }



    private float LinearDepth(float depth, float near, float far)
    {
        return (near * far) / (far - depth * (far - near));
    }

    private (float, float) toOrthogonal(float u, float v, float Z){

        float X = (float)(u - depthCamCalibration.cx) * (Z / depthCamCalibration.fx);
        float Y = (float)(v - depthCamCalibration.cy) * (Z / depthCamCalibration.fy);
        return (X, Y);
    }
    
}
