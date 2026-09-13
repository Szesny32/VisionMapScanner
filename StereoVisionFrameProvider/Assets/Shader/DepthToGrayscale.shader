Shader "Hidden/DepthToGrayscale"
{
    Properties
    {
        _MainTex ("Depth Texture", 2D) = "white" {}
        _MaxDistance ("Max Distance", Float) = 30.0
    }
    SubShader
    {
        Cull Off ZWrite Off ZTest Always
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata_t {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            sampler2D _MainTex;
            float _MaxDistance;

            v2f vert (appdata_t v) {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target {
                float rawDepth = SAMPLE_DEPTH_TEXTURE(_MainTex, i.uv);
                
                // Zwraca rzeczywistą odległość piksela od kamery w jednostkach Unity (metrach)
                float eyeDepth = LinearEyeDepth(rawDepth);
                
                // Skaluje dystans: to co bliżej niż _MaxDistance będzie szare/białe, to co dalej będzie odcięte (0)
                float depth01 = saturate(eyeDepth / _MaxDistance);
                
                // Odwrócenie: obiekty tuż przed kamerą (0) = 1 (biały), oddalone (_MaxDistance) = 0 (czarny)
                float invertedDepth = 1.0 - depth01;
                
                return fixed4(invertedDepth, invertedDepth, invertedDepth, 1.0);
            }
            ENDCG
        }
    }
}