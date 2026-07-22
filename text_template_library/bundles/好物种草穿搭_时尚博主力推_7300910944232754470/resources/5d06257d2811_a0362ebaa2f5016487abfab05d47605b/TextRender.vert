precision highp float;

attribute vec2 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform mat4 u_MVP;
uniform float u_Flag;
varying vec2 pp;
void main() 
{ 
    //gl_Position = u_MVP * position;
    vec2 pos = position;
    float flag = step(0.5, u_Flag);
    pos = mix(
        vec2(position.x,  position.y * mix(1.0, 2.0, step(0.0, position.y))),
        vec2(position.x * mix(1.0, 2.0, step(position.x, 0.0)),  position.y),
        flag
    );
    pp = pos;
    gl_Position = u_MVP * (vec4(pos.xy, 0.0, 1.0));
    uv0 = texcoord0;
    uv0.y = 1. - uv0.y;
    uv0 = mix(
        vec2(uv0.x, uv0.y * mix(1.0, 1.5, step(0.5, uv0.y))),
        vec2(1. - (1. - uv0.x) * mix(1.0, 1.5, step(uv0.x, 0.5)), uv0.y),
        flag
    );
}
