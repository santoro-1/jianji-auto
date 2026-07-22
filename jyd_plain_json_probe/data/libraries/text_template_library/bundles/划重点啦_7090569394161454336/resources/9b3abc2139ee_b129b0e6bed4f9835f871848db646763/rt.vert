attribute vec4 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform float expand_x_l;
uniform mat4 u_MVP;

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 myProj;
// uniform mat4 myView;

uniform mat4 u_Projection;

uniform float animing;

void main()
{
    vec4 newPos = position;

    // newPos.x *= .5;
    // newPos.y *= .5;

    gl_Position = u_MVP * newPos;

    uv0 = texcoord0;
    uv0.y = 1.0 - uv0.y;
}
