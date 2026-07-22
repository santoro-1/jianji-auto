precision highp float;

uniform sampler2D inputTexture2;
uniform vec2 texSize;
uniform float blurStep;
uniform vec4 u_ScreenParams;
varying vec2 uv0;

uniform float isBlur;
uniform float angle;

uniform float fade;
uniform float colll;

uniform float first_frame;

#define num 200

float Gaussian (float x)
{
    float sigma = 5.5;
    return exp(-(x*x) / (2.0 * sigma*sigma));
}
vec4 gauss_blur(sampler2D inputTexture, vec2 uv, float angle, float blurSize, vec2 uRenderSize)
{
    float radian = 3.1415926 * (angle) / 180.0;
    vec2 dir = vec2(cos(radian), sin(radian));


    vec4 result         = vec4(0.0);
    vec2 ratio = u_ScreenParams.xy/min(u_ScreenParams.x, u_ScreenParams.y);
    vec2 unit_uv        = vec2(blurSize) / (ratio * vec2(720.));
    vec4 centerPixel    = texture2D(inputTexture, uv);
    float sum_weight    = 1.;

    vec2 curPositiveCoordinate = uv;
    vec2 curNegativeCoordinate = uv;
    #ifdef SAMPLETIIMES2
    for(int i=1; i<=SAMPLETIIMES2; i++)
    {
        curPositiveCoordinate    += dir * unit_uv;
        curNegativeCoordinate    -= dir * unit_uv;
        float fX = Gaussian(float(i)/(float(num)/20.0));
        centerPixel += texture2D(inputTexture, curPositiveCoordinate) * fX;
        centerPixel += texture2D(inputTexture, curNegativeCoordinate) * fX;
        sum_weight += fX * 2.0;
    }
    #endif
    result = centerPixel / sum_weight;
    return result;
}

void main()
{
    vec2 uv1 = uv0;

   vec4 color = gauss_blur(inputTexture2, uv1, angle, blurStep, u_ScreenParams.xy);

    gl_FragColor = color ;

}
