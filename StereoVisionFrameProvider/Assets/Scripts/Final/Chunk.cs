using UnityEngine;
using System.Collections.Generic;

public class Chunk : MonoBehaviour
{
    private ParticleSystem particleSystem;
    private Octree octree;
    private float chunkSize = 1f;
    private int resolution = 8;

    public void Init(Vector3 position, int resolution = 8, float chunkSize = 1f)
    {
        transform.position = position;
        this.resolution = resolution;
        this.chunkSize = chunkSize;
        octree = new Octree(transform.position, resolution);
        particleSystem = GetComponent<ParticleSystem>();
    }

    public bool UpdateOctree(Vector3 point){
        return octree.Insert(point); 
    }

    public void RefreshVoxels() {
        (List<Vector3>positions , List<Color> colors, List<float> sizes) = octree.GetColoredLeafPositions();
        ParticleSystem.Particle[] voxels = new ParticleSystem.Particle[positions.Count];
        for(int i = 0; i < positions.Count; i++){
            voxels[i].position = positions[i] * chunkSize;
            voxels[i].startColor = colors[i];
            voxels[i].startSize = sizes[i];
        }
        particleSystem.SetParticles(voxels, voxels.Length);
    }

}
