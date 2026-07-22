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

void main(){

    gl_FragColor = vec4(0.0);
}
