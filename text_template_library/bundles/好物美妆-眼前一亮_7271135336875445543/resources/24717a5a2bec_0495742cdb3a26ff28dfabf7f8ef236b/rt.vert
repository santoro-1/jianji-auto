attribute vec2 position;
attribute vec2 texcoord0;
varying vec2 fTexCoord;
uniform mat4 u_MVP;
void main()
{
    fTexCoord.x = texcoord0.x;
    fTexCoord.y = texcoord0.y;
    gl_Position = u_MVP*vec4(position, 0.0, 1.0);
}