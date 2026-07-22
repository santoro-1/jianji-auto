precision highp float;

attribute vec2 position;
attribute vec2 texcoord0;
varying vec2 uv1;
varying vec2 uv0;
varying vec2 m;
varying vec2 n;
uniform vec4 u_ScreenParams;
uniform mat4 u_InvModel;
//uniform mat4 u_MVP;
void main() 
{ 
    //gl_Position = u_MVP * position;
    // gl_Position = sign(vec4(position.xy, 0.0, 1.0));
    // uv0 = texcoord0;
    // uv0.y = 1. - uv0.y;

    uv0 = texcoord0 * 2.0 - 1.0;
    gl_Position = vec4(uv0.xy, 0.0, 1.0);
    float y = (uv0.y / position.y);
    float x = (uv0.x / position.x);
    y = uv0.y - position.y;
    x = uv0.x - position.x;
    uv0.x *= u_ScreenParams.x / u_ScreenParams.y;
    uv0 = (u_InvModel * vec4(uv0, 0.0, 1.0)).xy;
    vec2 pos = vec2(position.x, (1. - (position.y * 0.5 + 0.5)) * 2.0 - 1.0);
    m = pos.xy;
    n = pos.xy * (texcoord0 * 2.0 - 1.0);
    uv1 = texcoord0;
}
