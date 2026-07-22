attribute vec4 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;

void main()
{
    vec4 newPos = position;
    // float num = 4.;
    // newPos.y+=step(0.,newPos.y)*2.*(num-1.)*newPos.y;
    gl_Position = u_MVP * newPos;
    uv0 = texcoord0;
    uv0.y = 1.0 - uv0.y;
    // heightN = num;
}
