precision highp float;
attribute vec2 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;
#define PI 3.1415926
void main() 
{ 
    vec4 pos = (vec4(texcoord0.xy * 2.0 - 1.0, 0.0, 1.0));
    // pos = pos;
    gl_Position = pos;
    uv0 = texcoord0;
}
