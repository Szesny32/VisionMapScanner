using System.Collections.Generic;
using UnityEngine;

public class OctreeManager : MonoBehaviour
{
    Octree octree;
    public VoxelRender voxelRender;
    float x , y,  z;
    Queue<Vector3> queue;
    int depth = 3;
    void Start()
    {
        queue =  new Queue<Vector3>();
        octree = new Octree(new Vector3(0.5f, 0.5f, 0.5f), depth);

        int a = (int)Mathf.Pow(2, depth);
        float range = Mathf.Pow(0.5f, depth);
        for(int i =0; i<2; i++){
            for(float x = range; x<=1f; x+=range){
                for(float y = range; y<=1f; y+=range){
                    for(float z = range; z<=1f; z+=range){
                        if(Random.Range(0f, 1f) >= 0.0f)
                            queue.Enqueue(new Vector3(x, y, z));
                    }   
                }
            }
        }




        Debug.Log(queue.Count);
    




    }

    // Update is called once per frame
    void Update()
    {
        if (Time.frameCount % 2 == 0 ){
            List<Vector3>vertices; 
            List<float> sizes;
            List<Color> colors;

            if(queue.Count!=0){
                Vector3 pos = queue.Dequeue();
                octree.Insert(pos);
                (vertices, colors, sizes) = octree.GetColoredLeafPositions();
                voxelRender.SetVoxels(vertices.ToArray(),colors.ToArray(), sizes.ToArray());
            }
      
        }
  
    }   




}
