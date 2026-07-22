precision highp float;
varying highp vec2 uv0;
uniform sampler2D _MainTex;
uniform sampler2D u_WordTex;

varying highp vec2 uv1;
varying highp vec2 m;
varying highp vec2 n;
uniform vec4 u_Time;
uniform float u_WordSize;
const int num = 25;
uniform vec4 u_ScreenParams;
uniform vec2 u_StartOffset;
uniform vec2 u_EndOffset;
uniform vec2 u_ShadowOffset;
uniform float u_Strength;
uniform float u_Size;
uniform float u_Interval;
uniform vec2 u_FlyInPos;
uniform float lastProgress;
uniform float shakeProgress;
uniform float fade;
uniform float blurStep;
varying vec2 v_CenterPos;
uniform float progress;

uniform vec2 trapezoid;
#define MOD3 vec3(.1031,.11369,.13787)

vec3 hash33(vec3 p3)
{
	p3 = fract(p3 * MOD3);
    p3 += dot(p3, p3.yxz+19.19);
    return fract(vec3((p3.x + p3.y)*p3.z, (p3.x+p3.z)*p3.y, (p3.y+p3.z)*p3.x));
}
float hash31(vec3 p3)
{
	p3 = fract(p3 * MOD3);
    p3 += dot(p3, p3.yxz+19.19);
    return fract(p3.x * p3.y * p3.z);
}
float random(in vec3 scale, in float seed) {
    /* use the fragment position for randomness */
    return fract(sin(dot(gl_FragCoord.xyz + seed, scale)) * 43758.5453 + seed);
}

vec4 scaleBlur(vec2 uv) {
    vec4 color = vec4(0.0);
    float total = 0.0;
	vec2 toCenter = vec2(-0.5, 0.5) - uv;
    float dissolve = 0.5;
    /* randomize the lookup values to hide the fixed number of samples */
    float offset3 = random(vec3(12.9898, 78.233, 151.7182), 0.0);

    for (int t = 0; t <= num; t++) {
        float percent = (float(t) + offset3 - .5) / float(num);
        float weight = 4.0 * (percent - percent * percent);

		vec2 curUV = uv + toCenter * percent * blurStep * progress;
        // vec2 uvT = vec2(1.0 - abs(abs(curUV.x) - 1.0), 1.0 - abs(abs(curUV.y) - 1.0));

        curUV.x = clamp(curUV.x, 0., 1.);
        curUV.y = clamp(curUV.y, 0., 1.);
        color += texture2D(u_WordTex, curUV) * weight;
        total += weight;
    }
    return color / total;
}
void main(void)
{
    //zhe kuai bu yong dong, shi pei yong//
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
    //----------------------------//
    gl_FragColor = scaleBlur(uv1);
}