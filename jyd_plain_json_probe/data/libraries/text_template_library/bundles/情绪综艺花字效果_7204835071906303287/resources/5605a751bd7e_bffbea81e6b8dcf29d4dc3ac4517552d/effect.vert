#version 300 es
layout(location=0) in vec4 position;
layout(location=1) in vec2 texcoord0;
layout(location=2) in vec2 texcoord1;
layout(location=3) in vec2 texcoord2;
layout(location=4) in vec4 charcolor;
layout(location=5) in vec2 texcoord3;
layout(location=6) in vec2 texcoord4;
layout(location=7) in vec2 texcoord5;
layout(location=8) in vec2 texcoord6;
out vec2 uv5;
out vec2 uv6;
out vec2 uv0;
out vec2 uv1;
out vec2 uv2;
out vec2 uv3;
out vec2 uv4;
out vec4 chcolor;
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
    uv5 = texcoord5;
    uv6 = texcoord6;
        chcolor = charcolor;
}
