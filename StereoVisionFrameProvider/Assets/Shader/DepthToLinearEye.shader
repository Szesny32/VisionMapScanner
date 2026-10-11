Shader "Hidden/DepthToLinearEye"
{
    Properties
    {
        _MainTex ("Depth Texture", 2D) = "white" {}
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
            float4 _DepthZParams;

            inline float LinearEyeDepthFromParams(float depth) {
                return 1.0 / (_DepthZParams.z * depth + _DepthZParams.w);
            }

            v2f vert (appdata_t v) {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                // Blit do RenderTexture odwraca obraz w pionie względem ścieżki kamer kolorowych.
                // Odwracamy współrzędną V, aby głębokość GT miała identyczną orientację jak kolor.
                o.uv = float2(v.uv.x, 1.0 - v.uv.y);
                return o;
            }

            fixed4 frag (v2f i) : SV_Target {
                float rawDepth = SAMPLE_DEPTH_TEXTURE(_MainTex, i.uv);

                // Zamiana depth buffer na rzeczywistą odległość Z od płaszczyzny kamery (metry)
                // Używamy parametrów projekcji kamery GT przekazanych jawnie, aby nie zależeć
                // od globalnego _ZBufferParams pozostawionego przez inną kamerę.
                float eyeDepth = LinearEyeDepthFromParams(rawDepth);

                // RFloat (R32F): liczy się tylko kanał R = odległość w metrach
                return fixed4(eyeDepth, eyeDepth, eyeDepth, 1.0);
            }
            ENDCG
        }
    }
}
