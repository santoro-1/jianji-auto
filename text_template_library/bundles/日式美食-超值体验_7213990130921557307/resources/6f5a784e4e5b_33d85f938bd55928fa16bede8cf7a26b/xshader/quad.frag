precision lowp float;
varying highp vec2 uv0;
uniform sampler2D _MainTex;
uniform float u_Amount;
uniform vec2 u_Center;
vec2 scale(vec2 uv, vec2 center, float size)
{
    uv -= center;
    uv *= size;
    return uv + center;

}
float n21(vec2 p,float seed){
    // p.x *= u_ScreenParams.x/u_ScreenParams.y;
    vec2 p3 = fract(p.yx*23.512);
    p3+=dot(p3,p3.yx+15.412+seed);
    return fract((p3.x+p3.y)*p3.x);
}
vec4 radialBlur(vec2 uv, float mode)
{
    const int SAMPLES = 32;
    vec4 ori = texture2D(_MainTex, uv);
    vec4 res = ori;
    float sumWeight = 1.0;
    float angle = u_Amount * 0.5;
    float size = u_Amount * 0.003;
    for (float i = 1.0; i <= 16.0; i += 1.0)
    {
        float n = n21(vec2(uv + i * size), 0.0) * 2.0 - 1.0;
        vec2 tmpUV1 = scale(uv, u_Center, 1.0 + size * i / 16.0 + n * size * 0.1);
        n = n21(vec2(-uv-i * size), 0.0) * 2.0 - 1.0;
        vec2 tmpUV2 = scale(uv, u_Center, 1.0 - i / 16.0 * size + n * size * 0.1);
        res += texture2D(_MainTex, tmpUV1);
        res += texture2D(_MainTex, tmpUV2);
        sumWeight += 2.0;
    }
    return vec4(res / sumWeight);
}
void main()
{
    gl_FragColor = radialBlur(uv0, 0.0);
}
