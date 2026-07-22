attribute vec4 position;
attribute vec4 charcolor;
attribute vec4 texcoord01;
attribute vec4 texcoord23;
attribute vec4 texcoord45;
attribute vec4 texcoord67;
varying vec4 chcolor;
varying vec4 WH;
varying vec4 char1;
varying vec4 dis_grad;
varying vec4 tex_ktv;
varying vec2 ktv_angle;
varying float smoothing_fwidth;
uniform mat4 u_MVP;
uniform mat4 u_Model;
uniform vec4 Offset_SquareSize;
void main()
{
    gl_Position = u_MVP * vec4(position.xy + Offset_SquareSize.xy, position.z, 1.0);
    float scale = length(u_Model[0]);
    smoothing_fwidth = texcoord67.z * gl_Position.w / scale;
    chcolor = charcolor;
    dis_grad.xy = texcoord01.xy;
    dis_grad.zw = (texcoord01.xy - texcoord01.zw)/(texcoord23.xy - texcoord01.zw);
    vec2 uvChar = ((texcoord01.xy - texcoord01.zw)/Offset_SquareSize.zw - 0.14)/0.72;
    tex_ktv.xy = uvChar * texcoord45.xy + texcoord23.zw;
    tex_ktv.zw = texcoord45.zw;
    ktv_angle = texcoord67.xy;
    WH = vec4(texcoord23.xy, texcoord01.zw);
    char1 = texcoord23;
    // chcolor = charcolor;
}
