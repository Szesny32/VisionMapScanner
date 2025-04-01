# 3D scene reconstruction based on stereovision
## Step 1: Stereovision
![image](https://github.com/user-attachments/assets/ecfd491c-b0e6-4ae7-95f9-03901d1cc062)


## Step 2: DepthMap*
![image](https://github.com/user-attachments/assets/a5899b8e-c8ba-48d4-b140-6f0b52bb0d48)
* Current results are presented for the ideal depth map obtained from the Unity renderer, not determined from the stereovision system (with openCV). 
The functionality will be enabled when the higher layers becomes fully operational & efficient. 


## Step 3: Data Structure - Sparse Voxel Octree
![octree](https://github.com/user-attachments/assets/668a73ad-e7b8-445b-9fa8-c22b69892ff5)


## Step 4: 3D Scene Reconstruction
![3d_reconstruction](https://github.com/user-attachments/assets/f7198e6c-7c56-439f-b1c0-57baae892e46)
* The current result operates only on one chunk (1x1x1) - the rest is truncated. 

## Step 5: Chunking Scene Reconstruction System
![ezgif-52a6e0a74a24d6](https://github.com/user-attachments/assets/5f08780c-bbda-4bc4-bcf9-fe92528fa6ac)
* The current phase still needs to be adjusted (scaling, central chunk problem and the optimization problem)
