attribute vec4 position;
attribute vec2 texcoord0;
attribute vec2 texcoord1;
attribute vec2 texcoord2;
attribute vec4 charcolor;
attribute vec2 texcoord3;
attribute vec2 texcoord4;
varying vec2 uv0;
varying vec2 uv1;
varying vec2 uv2;
varying vec2 uv3;
varying vec2 uv4;
varying vec4 chcolor;
uniform mat4 u_MVP;
uniform vec2 _ShadowOffset;
void main() 
{ 
    gl_Position = u_MVP * vec4(position.xy + _ShadowOffset, position.z, position.w);
    uv0 = texcoord0;
    uv1 = texcoord1;
    uv2 = texcoord2;
    uv3 = texcoord3;
    uv4 = texcoord4;
    chcolor = charcolor;
}
