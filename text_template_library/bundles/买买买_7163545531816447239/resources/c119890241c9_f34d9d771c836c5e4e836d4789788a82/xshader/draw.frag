precision highp float;
varying highp vec2 uv0;
uniform sampler2D u_TextTexture;
uniform float u_AllAlpha;
#define PI 3.1415926

void main(){

    gl_FragColor = texture2D(u_TextTexture, uv0) * u_AllAlpha;
}
