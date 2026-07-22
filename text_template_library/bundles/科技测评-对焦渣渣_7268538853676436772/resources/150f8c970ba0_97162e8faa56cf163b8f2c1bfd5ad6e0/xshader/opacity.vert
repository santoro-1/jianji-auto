precision highp float;

uniform mat4 u_MVP;

attribute vec4 a_position;
attribute vec2 a_texcoord0;

varying vec2 v_uv;


void main() {
    v_uv = vec2(a_texcoord0.x, 1.0 - a_texcoord0.y);
    gl_Position = u_MVP * a_position;
}
