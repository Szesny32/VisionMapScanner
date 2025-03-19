using System.Collections.Generic;
using UnityEngine;

public class Octree 
{
    public class Node{
        public Dictionary<byte, Node> Children = new Dictionary<byte, Node>();
        public bool isLeaf => Children.Count == 0;
    }

    Node root;

    public Octree(){
        root = new Node();
    }

    public void Insert(int depth, Vector3 position){
        Node node = root;
        Vector3 center = new Vector3(0.5f, 0.5f, 0.5f);
        
        for(int i = 1; i <= depth; i++){
            byte index = ChildIndex(position, center);
            //Debug.Log($"{position} -> {index}");
            if(!node.Children.ContainsKey(index)) {
                node.Children[index] =  new Node();
            }
            node = node.Children[index];
            center = ChildCenter(index, i, center);
        }
    }

    private Vector3 GetCenter(Vector3 position, int depth){
        Vector3 center = new Vector3(0.5f, 0.5f, 0.5f);
        for(int i = 1; i <= depth; i++){
            byte index = ChildIndex(position, center);
            center = ChildCenter(index, i, center);
        }
        return center;
    }

    private static float Range(int depth) => Mathf.Pow(0.5f, depth+1);
    private static Vector3 ChildCenter(byte childIndex, int childDepth, Vector3 parentCenter){
        float childRange = Range(childDepth);
        Vector3 childCenter = parentCenter + new Vector3(
            (childIndex & 0b00000100) != 0? childRange: -childRange,
            (childIndex & 0b00000010) != 0? childRange: -childRange,
            (childIndex & 0b00000001) != 0? childRange: -childRange
        );
        //Debug.Log($"{childCenter} = ChildCenter(byte childIndex={childIndex}, int childDepth={childDepth}, Vector3 parentCenter)={parentCenter}");
        return childCenter;
    }

    private static byte ChildIndex(Vector3 position, Vector3 center){
        byte index = 0b00000000;
        if(position.x > center.x) index |= 0b00000100; 
        if(position.y > center.y) index |= 0b00000010; 
        if(position.z > center.z) index |= 0b00000001;
        return index;
    }

    public List<Vector3> GetLeafPositions() {
        List<Vector3> positions = new List<Vector3>();
        Stack<(int, Vector3, Node)> stack = new Stack<(int, Vector3, Node)>();
        stack.Push((0, new Vector3(0.5f, 0.5f, 0.5f), root));
        while(stack.Count > 0) {
            (int depth, Vector3 center, Node node) = stack.Pop();
            if(node.isLeaf) {
                positions.Add(center);
                continue;
            }
            foreach (var kvp in node.Children) {
                byte childIndex = kvp.Key;
                Node childNode = kvp.Value;
                stack.Push((depth+1, ChildCenter(childIndex, depth+1, center), childNode));
            }
        }
        return positions;
    }

}
