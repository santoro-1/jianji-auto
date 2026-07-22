attribute vec4 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;
uniform mat4 u_VP;
uniform mat4 u_Model;

varying vec2 m;
varying vec2 n;
varying vec2 uvn;
varying vec2 uv1;
void main()
{
    vec4 newPos = position;
    // float num = 4.;
    // newPos.y+=step(0.,newPos.y)*2.*(num-1.)*newPos.y;
    gl_Position = vec4(texcoord0 * 2.0 - 1.0, 0.0, 1.0);
    // gl_Position = position;
    gl_Position.z = 0.;
    uvn = position.xy * 0.5 + 0.5;
    uv0 = texcoord0;
    vec2 pos = vec2(position.x, (1. - (position.y * 0.5 + 0.5)) * 2.0 - 1.0);
    m = pos.xy;
    n = pos.xy * (texcoord0 * 2.0 - 1.0);
    uv1 = texcoord0;
    // uv0.y = 1.0 - uv0.y;
    // heightN = num;
}
