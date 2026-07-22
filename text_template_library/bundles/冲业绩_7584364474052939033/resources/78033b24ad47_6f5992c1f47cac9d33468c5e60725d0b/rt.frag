precision highp float;

varying vec2 uv0;

uniform sampler2D _MainTex;

uniform float s1;
uniform float b1;

uniform float s2;
uniform float b2;
uniform float a2;

const vec2 u_Center = vec2(0.5);
uniform vec4 textSize;
const float u_Quality = 10.;


float n21(vec2 p,float seed){
    // p.x *= u_ScreenParams.x/u_ScreenParams.y;
    vec2 p3 = fract(p.yx*23.512);
    p3+=dot(p3,p3.yx+15.412+seed);
    return fract((p3.x+p3.y)*p3.x);
}

vec2 scale(vec2 uv, vec2 center, float size)
{
    uv -= center;
    uv *= size;
    return uv + center;

}

vec4 radialBlur(sampler2D u_InputTex, vec2 uv, float u_Amount)
{
    const int SAMPLES = 32;
    vec4 ori = texture2D(u_InputTex, uv);
    vec4 res = ori;
    float sumWeight = 1.0;
    float angle = u_Amount * 0.5;
    float size = u_Amount * 0.003;
    for (float i = 1.0; i <= 32.0; i += 1.0)
    {
        float n = n21(vec2(uv + i * size), 0.0) * 2.0 - 1.0;
        // n *= 0.;
        vec2 tmpUV1 = scale(uv, u_Center, 1.0 + size * i / 32.0 + n * size * 0.1);
        n = n21(vec2(-uv-i * size), 0.0) * 2.0 - 1.0;
        // n *= 0.;
        vec2 tmpUV2 = scale(uv, u_Center, 1.0 - i / 32.0 * size + n * size * 0.1);
        res += texture2D(u_InputTex, tmpUV1);
        res += texture2D(u_InputTex, tmpUV2);
        sumWeight += 2.0;
    }
    return vec4(res.rgb / sumWeight, ori.a);
}

vec4 radiusBlurScale(sampler2D img, float aspect, vec2 uv, float degree, vec2 center)
{
    vec4 result = vec4(0.0, 0.0, 0.0, 0.0);
    result += texture2D(img, uv);
    const int sampleTimes = 30;
    vec2 uv0 = uv;
    uv0 -= center;
    uv0 /= vec2(1.0, aspect);
    for (int i = 1; i <= sampleTimes; i++)
    {
        float scale = float(i) / float(sampleTimes) * 0.25 * degree / 100.0;
        vec2 uv1 = uv0 * (1.0 - scale);
        uv1 *= vec2(1.0, aspect);
        uv1 += center;
        result += texture2D(img, uv1);

        vec2 uv2 = uv0 * (1.0 + scale);
        uv2 *= vec2(1.0, aspect);
        uv2 += center;
        result += texture2D(img, uv2);
    }
    result /= float(sampleTimes * 2 + 1);
    return result;
}


void main()
{
    vec2 uv1 = uv0;
    uv1 -= 0.5;
    uv1 /= s1;
    uv1 += 0.5;
    vec4 col1 = radiusBlurScale(_MainTex, textSize.x/textSize.y, uv1, b1, vec2(0.5));

    vec2 uv2 = uv0;
    uv2 -= 0.5;
    uv2 /= s2;
    uv2 += 0.5;
    vec4 col2 = radiusBlurScale(_MainTex, textSize.x/textSize.y, uv2, b2, vec2(0.5));
    col2 *= a2;

    vec4 res = col2;
    res += col1;


    
    gl_FragColor = res;
}
