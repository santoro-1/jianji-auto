precision highp float;

attribute vec2 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;
uniform mat4 u_Model;
uniform mat4 u_VP;
uniform vec2 u_Anchor_4;
uniform vec2 u_Anchor1_4;
uniform float u_AnchorScale_4;
uniform float u_AnchorAngle_4;
uniform vec2 u_Ofs_4;
uniform float u_Angle_4;
uniform float u_Scale_4;
uniform float u_Alpha_4;
varying float v_Alpha;
#define PI 3.1415926
vec2 rotate(vec2 pos, float angle)
{
    float theta = angle / 180. * PI;
    float cost = cos(theta);
    float sint = sin(theta);
    return mat2(cost, sint, -sint, cost) * pos;
}
void main() 
{ 
    //gl_Position = u_MVP * position;
    vec4 pos = (vec4(position.xy, 0.0, 1.0));
    pos.xy -= u_Anchor_4;
    pos.xy = rotate(pos.xy, u_Angle_4 + 0.0);
    pos.xy *= u_Scale_4;
    pos.xy += u_Ofs_4 + u_Anchor_4;
    pos.xy -= u_Anchor_4;
    pos.xy = rotate(pos.xy, u_AnchorAngle_4);
    pos.xy *= u_AnchorScale_4;
    pos.xy += u_Anchor_4 - u_Anchor1_4;
    pos = u_MVP * pos;
    gl_Position = pos;
    uv0 = texcoord0;
    uv0.y = 1. - uv0.y;
    v_Alpha = u_Alpha_4;
}
