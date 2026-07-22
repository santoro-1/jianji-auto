precision highp float;

attribute vec2 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;
uniform mat4 u_Model;
uniform mat4 u_VP;
uniform vec2 u_Anchor;
uniform vec2 u_Anchor1;
uniform float u_AnchorScale;
uniform float u_AnchorAngle;
uniform vec2 u_Ofs2;
uniform float u_Angle2;
uniform vec2 u_Scale2;
uniform float u_Strength2;
varying float v_Strength;
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
    // pos.xy -= u_Anchor;
    pos.xy = rotate(pos.xy, u_Angle2);
    pos.xy *= u_Scale2;
    pos.xy += u_Ofs2;
    // pos.xy = rotate(pos.xy, u_AnchorAngle);
    // pos.xy *= u_AnchorScale;
    // pos.xy -= u_Anchor1;
    pos = u_MVP * pos;
    gl_Position = pos;
    // gl_Position.xy = texcoord0 * 2.0 - 1.0;
    uv0 = texcoord0;
    uv0.y = 1. - uv0.y;
    v_Strength = u_Strength2;
}
