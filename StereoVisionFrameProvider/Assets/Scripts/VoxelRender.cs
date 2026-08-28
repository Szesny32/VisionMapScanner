using UnityEngine;

[RequireComponent(typeof(ParticleSystem))]
public class VoxelRender : MonoBehaviour {
    ParticleSystem system;
    ParticleSystem.Particle[] voxels;
     bool voxelsUpdated = false;
    private float voxelScale = 0.01f;
    private float scale = 1f;

    void Start() => system = GetComponent<ParticleSystem>();
 
    void Update() {
        if(voxelsUpdated) {
            system.SetParticles(voxels, voxels.Length);
            voxelsUpdated = false;
        }
    }
    
    public void SetVoxels(Vector3[] positions, Color[] colors, float voxelScale) {
        voxels = new ParticleSystem.Particle[positions.Length];
        for(int i = 0; i < positions.Length; i++){
            voxels[i].position = positions[i] *scale;
            voxels[i].startColor = colors[i];
            voxels[i].startSize = voxelScale;
        }
        //Debug.Log("Voxels set! Voxel count: " + voxels.Length);
        voxelsUpdated = true;
    }

        public void SetVoxels(Vector3[] positions, float[] sizes) {
        voxels = new ParticleSystem.Particle[positions.Length];
        for(int i = 0; i < positions.Length; i++){
            voxels[i].position = positions[i] *scale;
            voxels[i].startColor = new Color(1f- (float)i/positions.Length, 0, (float)i/positions.Length);
            voxels[i].startSize = sizes[i];
        }
        Debug.Log("Voxels set! Voxel count: " + voxels.Length);
        voxelsUpdated = true;
    }

    public void SetVoxels(Vector3[] positions, Color[] color, float[] sizes) {
        voxels = new ParticleSystem.Particle[positions.Length];
        for(int i = 0; i < positions.Length; i++){
            voxels[i].position = positions[i] *scale;
            voxels[i].startColor = color[i];
            voxels[i].startSize = sizes[i];
        }
        Debug.Log("Voxels set! Voxel count: " + voxels.Length);
        voxelsUpdated = true;
    }

    
}
