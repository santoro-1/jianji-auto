attribute vec4 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;
uniform vec4 _MainTex_ST;

void main()
{
    gl_Position = u_MVP * position;
    uv0 = texcoord0;
    uv0.y = 1.0 - uv0.y;
}
