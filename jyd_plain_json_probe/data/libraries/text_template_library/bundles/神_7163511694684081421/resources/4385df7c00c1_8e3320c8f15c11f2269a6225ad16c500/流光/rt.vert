attribute vec4 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;
uniform highp vec4 texSize;

void main()
{
    //vec2 screenSize = vec2(baseTexWidth,baseTexHeight);
    vec4 newPos = position;
    float num = 3.;
    newPos.y*=2.;
    newPos.x*=2.;
    gl_Position = u_MVP * newPos;
    uv0 = texcoord0;
    uv0.y = 1.0 - uv0.y;
}
