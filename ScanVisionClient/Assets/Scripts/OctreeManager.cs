using System.Collections.Generic;
using UnityEngine;

public class OctreeManager : MonoBehaviour
{
    Octree octree;
    public VoxelRender voxelRender;
    
    void Start()
    {
        octree = new Octree();
        int depth = 2;
        int a = (int)Mathf.Pow(2, depth);
        float size = Mathf.Pow(0.5f, depth);
        float range = Mathf.Pow(0.5f, depth+1);

        for(float x = range; x<1f; x+=range){
            for(float y = range; y<1f; y+=range){
                for(float z = range; z<1f; z+=range){
                    if(Random.Range(0f, 1f) > 0.8f)
                        octree.Insert(depth, new Vector3(x, y, z));
                }   
            }
        }
    

        List<Vector3>vertices = octree.GetLeafPositions();
        voxelRender.SetVoxels(vertices.ToArray(), size);


    }

    // Update is called once per frame
    void Update()
    {
        
    }   




}
