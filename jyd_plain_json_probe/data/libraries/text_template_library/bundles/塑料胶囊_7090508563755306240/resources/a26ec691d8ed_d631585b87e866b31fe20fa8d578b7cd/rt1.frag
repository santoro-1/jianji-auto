precision highp float;
varying highp vec2 uv0;
varying highp float heightN;
varying vec2 uvn;
varying highp vec2 uv1;
varying highp vec2 m;
varying highp vec2 n;
uniform sampler2D inputTex;

uniform float blurSize_all;

uniform float yoffset;
uniform float gap;
uniform float progress;
// uniform float softmask;
uniform float appear;

vec4 gauss_blur(sampler2D inputTexture, vec2 uv, float blurSize)
{
    float half_gaussian_weight[9];

    half_gaussian_weight[0]= 0.2;   //0.2;//0.137401;
    half_gaussian_weight[1]= 0.19;  //0.2;//0.125794;
    half_gaussian_weight[2]= 0.17;  //0.2;//0.106483;
    half_gaussian_weight[3]= 0.15;  //0.2;//0.080657;
    half_gaussian_weight[4]= 0.13;  //0.2;//0.054670;
    half_gaussian_weight[5]= 0.11;  //0.2;//0.033159;
    half_gaussian_weight[6]= 0.08;  //0.2;//0.017997;
    half_gaussian_weight[7]= 0.05;  //0.2;//0.008741;
    half_gaussian_weight[8]= 0.02;  //0.2;//0.003799;
    
    vec2 dir = vec2(0., 1.);

    vec4 sum            = vec4(0.0);
    vec4 result         = vec4(0.0);
    vec2 unit_uv        = vec2(blurSize / 1000., blurSize / 1000.);
    // vec2 unit_uv        = vec2(0., 0.);
    vec4 centerPixel    = texture2D(inputTexture, uv) * half_gaussian_weight[0];
    float sum_weight    = half_gaussian_weight[0];

    vec2 curPositiveCoordinate = uv;
    vec2 curNegativeCoordinate = uv;

    for(int i=1; i<=8; i++)
    {
        curPositiveCoordinate    += dir * unit_uv;
        curNegativeCoordinate    -= dir * unit_uv;
        sum += texture2D(inputTexture, curPositiveCoordinate) * half_gaussian_weight[i];
        sum += texture2D(inputTexture, curNegativeCoordinate) * half_gaussian_weight[i];
        sum_weight += half_gaussian_weight[i] * 2.0;
    }
    
    result = (sum + centerPixel) / sum_weight;
    return result;
}

vec4 directionBlur(sampler2D tex, vec2 uv, vec2 directionOfBlur, float intensity)
{
    vec2 pixelStep = vec2(1.0/1000. * intensity);
    float dircLength = length(directionOfBlur);
	pixelStep.x = directionOfBlur.x * 1.0 / dircLength * pixelStep.x;
	pixelStep.y = directionOfBlur.y * 1.0 / dircLength * pixelStep.y;


	vec4 color = vec4(0);
    const int num = 13;
	for(int i = -num; i <= num; i++)
	{
       vec2 blurCoord = uv + pixelStep * float(i);
	   vec2 uvT = vec2(1.0 - abs(abs(blurCoord.x) - 1.0), 1.0 - abs(abs(blurCoord.y) - 1.0));
	   color += texture2D(tex, uvT);
	}
	color /= float(2 * num + 1);	
    color ;
	return color;
}

float remap(float a, float b, float x)
{
    return (b - a) * x + a;
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
    // vec2 uvy = uv0;
    // uvy.y -= 0.5;
    // uvy.y *= 1./(1. - gap * 2.0);
    // uvy.y += .5;

    // uvy.y = fract(uvy.y + yoffset);
    // uvy.y = remap(gap, 1. - gap, uvy.y);
    gl_FragColor = directionBlur(inputTex, uv0, vec2(0., 1.), blurSize_all);
    // gl_FragColor = texture2D(inputTex, uv0);
    // gl_FragColor = vec4(uv0,0,1);
    // gl_FragColor *= smoothstep(x.y, x.y-0.5, uv0.y*2.-1.) * smoothstep(y.y, y.y+0.5, uv0.y*2.-1.);
    // gl_FragColor *= smoothstep(x.y+0.5, x.y, uv0.y*2.-1.) * smoothstep(y.y-0.5, y.y, uv0.y*2.-1.);
    gl_FragColor *= smoothstep(0., appear+0.01, progress);
    // gl_FragColor = vec4(uvn, 0,1);
    // gl_FragColor = vec4(uv0, 0,1);
}