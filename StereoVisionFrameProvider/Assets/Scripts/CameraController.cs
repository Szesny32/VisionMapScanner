using UnityEngine;

public class CameraController : MonoBehaviour
{
    public Transform target; // Obiekt, wokół którego kamera ma się obracać
    public float speed = 20f; 

    void Update()
    {
        transform.RotateAround(target.position, Vector3.up, speed * Time.deltaTime);
        transform.LookAt(target); 
    }

}
