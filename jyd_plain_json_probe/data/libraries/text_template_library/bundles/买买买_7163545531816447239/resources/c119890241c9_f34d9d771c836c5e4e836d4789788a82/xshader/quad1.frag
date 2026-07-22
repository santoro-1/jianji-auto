precision highp float;
varying highp vec2 uv0;
uniform sampler2D u_albedo;
uniform sampler2D _MainTex;
uniform vec4 u_ScreenParams;
uniform vec2 u_TextRect;
uniform float u_Strength;
uniform vec2 u_Center;
#define PI 3.1415926

void main()
{
    vec4 resColor = texture2D(_MainTex, uv0);
    vec2 dir = vec2(0.0, 1.0) / u_TextRect.xy;
    float sumWeight = 1.0;
    for (int i = 1;i <= 24; ++i)
    {
        float weight = pow(float(24 - i) / 24.0, 0.2);
        vec2 uv = uv0 - dir * float(i) * u_Strength;
        resColor += texture2D(_MainTex, uv) * weight;
        uv = uv0 + dir * float(i) * u_Strength;
        resColor += texture2D(_MainTex, uv) * weight;
        sumWeight += 2.0;
    }
    gl_FragColor = resColor / sumWeight;
}
