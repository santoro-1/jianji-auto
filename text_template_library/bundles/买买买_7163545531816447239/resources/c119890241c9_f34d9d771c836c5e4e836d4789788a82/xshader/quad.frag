precision highp float;
varying highp vec2 uv0;
uniform sampler2D u_albedo;
uniform sampler2D _MainTex;
uniform vec4 u_ScreenParams;
uniform vec2 u_TextRect;
uniform float u_Strength;
uniform float u_Strength1;
uniform vec2 u_Center;
varying float v_Alpha;
uniform float u_TrailAlpha;
uniform float u_Offset;
uniform float u_RowNum;
uniform float u_cNum;
uniform vec4 u_Time;
uniform float u_Progress;
#define PI 3.1415926

void main()
{   
    // vec2 uv = uv0 + vec2(sin(uv0.y * PI * 6.0 * u_RowNum + u_Progress * 16.) * (0.0075 / u_cNum), 0.0);
    // vec2 uv1 = uv0;
    // uv1 -= .5;
    // uv1 *= 0.9;
    // uv1 += .5;
    // uv1 = uv1 + vec2(sin(uv1.y * PI * 6.0 * u_RowNum + u_Progress * 16. + 1.9) * (0.0075 / u_cNum), 0.0);
    vec4 color1 = texture2D(_MainTex, uv0);
    // vec4 color2 = texture2D(_MainTex, uv1) * 0.0;
    gl_FragColor = color1 * v_Alpha;
}
