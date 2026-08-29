using UnityEngine;

public class CameraOrbit : MonoBehaviour
{
    public Transform target;
    public float distance = 5f; 
    public float speed = 20f;

    private float currentAngle = 0f;

    void Update()
    {
        if (target == null) return;

        currentAngle += speed * Time.deltaTime;

        float rad = currentAngle * Mathf.Deg2Rad;
        float x = target.position.x + Mathf.Cos(rad) * distance;
        float z = target.position.z + Mathf.Sin(rad) * distance;
        float y = target.position.y;

        transform.position = new Vector3(x, y, z);
        transform.LookAt(target);
    }
}