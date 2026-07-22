attribute vec4 position;
attribute vec2 texcoord0;
varying vec2 uv0;
uniform float expand_x_l;
uniform mat4 u_MVP;

uniform mat4 u_Model;
uniform mat4 u_VP;
uniform mat4 u_View;
uniform mat4 myProj;
// uniform mat4 myView;

uniform mat4 u_Projection;

uniform float animing;

void main()
{
    vec4 newPos = position;
    mat4 new_M = mat4(u_Model);
    new_M[3][0] = 0.;
    new_M[3][1] = 0.;
    // new_M[3][2] = 0.;
    if(animing > 0.5){
        vec4 tmp = myProj * u_View * new_M * newPos;
        gl_Position = tmp + u_Projection * u_View * (vec4(u_Model[3][0], u_Model[3][1], 0.0, .0)) * tmp.w;
    }else{
        // newPos.x -= 1.0;
        gl_Position = u_MVP * newPos;
    }

    uv0 = texcoord0;
    uv0.y = 1.0 - uv0.y;
}
