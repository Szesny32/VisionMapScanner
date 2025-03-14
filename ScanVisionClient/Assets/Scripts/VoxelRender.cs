using UnityEngine;

[RequireComponent(typeof(ParticleSystem))]
public class VoxelRender : MonoBehaviour {
    ParticleSystem system;
    ParticleSystem.Particle[] voxels;
    bool voxelsUpdated = false;
    public float voxelScale = 0.1f;
    public float scale = 1f;

    void Start() => system = GetComponent<ParticleSystem>();
 
    void Update() {
        if(voxelsUpdated) {
            system.SetParticles(voxels, voxels.Length);
            voxelsUpdated = false;
        }
    }
    
    public void SetVoxels(Vector3[] positions, Color[] colors) {
        voxels = new ParticleSystem.Particle[positions.Length];
        for(int i = 0; i < positions.Length; i++){
            voxels[i].position = positions[i] *scale;
            voxels[i].startColor = colors[i];
            voxels[i].startSize = voxelScale;
        }
        Debug.Log("Voxels set! Voxel count: " + voxels.Length);
        voxelsUpdated = true;
    }
    
}
