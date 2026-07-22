precision highp float;
varying highp vec2 uv0;
uniform sampler2D inputTex;
// uniform float u_blurSize;
// uniform float appear;
// uniform vec2 ratio;
varying vec2 m;
varying vec2 n;
varying vec2 uv1;
uniform sampler2D _MainTex;
uniform vec4 u_ScreenParams;
uniform highp vec4 texSize;
uniform float _time;
uniform float flag;
float texLightFlag(float samplerTexCoord,float t){
    float width = 0.25;
    float mid = 1.2*t;
    float d = smoothstep(mid-width,mid,1.0-samplerTexCoord)*smoothstep(mid+width,mid,1.0-samplerTexCoord);

    return (1.+0.5*d)*(smoothstep(t+0.1,t,1.0-samplerTexCoord));
}

float n21(vec2 p){
    return fract(sin(p.x*100.+p.y*168.)*2368.)*0.15+0.85;
}
void main(void)
{
    vec2 uv = uv0;
    vec2 x = vec2(0.0);
    vec2 y = vec2(0.0);
    x = (m + n) / (2.0 * (uv1));
    y = (m - n) / (2.0 * (1. - uv1));
    float width = x.x - y.x;
    float height = x.y - y.y;
    uv.x -= (x.x + y.x) * 0.5;
    uv.y += (x.y + y.y) * 0.5;
    uv.x /= (width * 0.5);
    uv.y /= (height * 0.5);
    uv = uv * 0.5 + 0.5;

    vec4 lightResult = vec4(0.0);
    vec2 offset = vec2(1.)/u_ScreenParams.xy;
    vec4 lightCol = texture2D(inputTex,uv1);
    float blurSize=2.5;
    lightCol=(lightCol+texture2D(inputTex,uv1+vec2(blurSize,0.0)*offset)+texture2D(inputTex,uv1+vec2(-blurSize,0.0)*offset)
    +texture2D(inputTex,uv1+vec2(0.0,blurSize)*offset)+texture2D(inputTex,uv1+vec2(0.0,-blurSize)*offset)+
    texture2D(inputTex,uv1+vec2(0.5*blurSize,-0.5*blurSize)*offset)+texture2D(inputTex,uv1+vec2(0.5*blurSize,0.5*blurSize)*offset)+
    texture2D(inputTex,uv1+vec2(-0.5*blurSize,-0.5*blurSize)*offset)+texture2D(inputTex,uv1+vec2(-0.5*blurSize,0.5*blurSize)*offset))/9.;

    vec4 texCol = texture2D(_MainTex,uv);
    float axis = mix(1.0-uv.x,uv.y,flag);
    texCol = texCol*texLightFlag(axis,_time);
    float lightNoise = n21(uv);
    gl_FragColor = lightCol*lightNoise*((1.0-texCol.a)*0.8+0.2)+texCol;
    gl_FragColor = gl_FragColor*smoothstep(-0.001-0.5,0.001-0.5,uv.x)*(1.0-smoothstep(0.999+0.5,1.000+0.5,uv.x))*smoothstep(-0.001-0.5,0.001-0.5,uv.y)*(1.0-smoothstep(0.999+0.5,1.000+0.5,uv.y));
    //gl_FragColor = vec4(lightMask(uv,_time));
}

