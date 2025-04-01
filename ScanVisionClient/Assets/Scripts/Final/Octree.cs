using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class Octree 
{
    public class Node{
        public Dictionary<byte, Node> Children = new Dictionary<byte, Node>();
        public bool isLeaf = false;
    }

    private Node root;
    private Vector3 center;
    private int resolution = 8;
    private float chunkSize = 1f;

    public Octree(Vector3 center, int resolution = 8, float chunkSize = 1f){
        root = new Node();
        this.center = center;
        this.resolution = resolution;
        this.chunkSize = chunkSize;
    }

    public bool Insert(Vector3 position){
        return Insert(position, resolution);
    }

    public bool Insert(Vector3 point, int depth){

        if(!IsInside(point)) return false;
        Node node = root;
        Vector3 childCenter = center;

        Stack<Node> path = new Stack<Node>();

        for(int i = 1; i <= depth; i++){
            path.Push(node);
            if(node.isLeaf) return false;
            byte index = ChildIndex(point, childCenter);
            if(!node.Children.ContainsKey(index)) {
                node.Children[index] =  new Node();
                if(i == depth) node.Children[index].isLeaf = true;
            } 
            
            node = node.Children[index];
            childCenter = ChildCenter(index, i, childCenter);
        }

        while (path.Count > 0) {
            Node parent = path.Pop();
            if (!tryMerge(parent)) break;
        }
        return true;
    }


    private bool IsInside(Vector3 point){
        float range = chunkSize/2;
        return IsInside(center.x, range, point.x) && IsInside(center.y, range, point.y) && IsInside(center.z, range, point.z);
    }

    //TODO: Potential duplication of limit values
    private bool IsInside(float center, float range, float point){
        return point >= center - range && point <= center + range;
    }

    private bool tryMerge(Node node){
        if(node.Children.Count != 8 || node.Children.Values.Any(child => !child.isLeaf)) return false;
        node.Children.Clear();
        node.isLeaf = true;
        return true;
    }

    private Vector3 GetCenter(Vector3 position, int depth){
        Vector3 childCenter = center;
        for(int i = 1; i <= depth; i++){
            byte index = ChildIndex(position, childCenter);
            childCenter = ChildCenter(index, i, childCenter);
        }
        return childCenter;
    }

    private static float Range(int depth) => Mathf.Pow(0.5f, depth+1);
    private static Vector3 ChildCenter(byte childIndex, int childDepth, Vector3 parentCenter){
        float childRange = Range(childDepth);
        Vector3 childCenter = parentCenter + new Vector3(
            (childIndex & 0b00000100) != 0? childRange: -childRange,
            (childIndex & 0b00000010) != 0? childRange: -childRange,
            (childIndex & 0b00000001) != 0? childRange: -childRange
        );
        return childCenter;
    }

    private static byte ChildIndex(Vector3 position, Vector3 parentCenter){
        byte index = 0b00000000;
        if(position.x > parentCenter.x) index |= 0b00000100; 
        if(position.y > parentCenter.y) index |= 0b00000010; 
        if(position.z > parentCenter.z) index |= 0b00000001;
        return index;
    }

    public (List<Vector3>, List<Color>, List<float>) GetColoredLeafPositions() {
        List<Vector3> positions = new List<Vector3>();
        List<float> sizes = new List<float>();
        List<Color> colors = new List<Color>();
        Stack<(int, Vector3, Node)> stack = new Stack<(int, Vector3, Node)>();
        stack.Push((0, new Vector3(0.5f, 0.5f, 0.5f), root));
        while(stack.Count > 0) {
            
            (int depth, Vector3 center, Node node) = stack.Pop();
            if(node.isLeaf) {
                positions.Add(center);
                sizes.Add(Mathf.Pow(0.5f, depth));
                colors.Add(new Color(center.x, center.y, center.z));
                
                continue;
            }
            foreach (var kvp in node.Children) {
                byte childIndex = kvp.Key;
                Node childNode = kvp.Value;
                stack.Push((depth+1, ChildCenter(childIndex, depth+1, center), childNode));
            }
        }
        return (positions, colors, sizes);
    }
    
    public (List<Vector3>, List<float>) GetLeafPositions() {
        List<Vector3> positions = new List<Vector3>();
        List<float> sizes = new List<float>();
        Stack<(int, Vector3, Node)> stack = new Stack<(int, Vector3, Node)>();
        stack.Push((0, center, root));
        while(stack.Count > 0) {
            
            (int depth, Vector3 center, Node node) = stack.Pop();
            if(node.isLeaf) {
                positions.Add(center);
                sizes.Add(Mathf.Pow(0.5f, depth));
                
                continue;
            }
            foreach (var kvp in node.Children) {
                byte childIndex = kvp.Key;
                Node childNode = kvp.Value;
                stack.Push((depth+1, ChildCenter(childIndex, depth+1, center), childNode));
            }
        }
        return (positions, sizes);
    }

}
