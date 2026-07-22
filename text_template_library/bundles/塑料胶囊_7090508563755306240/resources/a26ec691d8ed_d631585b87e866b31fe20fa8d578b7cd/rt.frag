precision highp float;
varying highp vec2 uv0;
varying highp float heightN;
uniform sampler2D _MainTex;

uniform float blurSize_all;

uniform float yoffset;
uniform float gap;
uniform float softmask;

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
    vec2 uv1 = uv0;
    vec2 uv2 = uv0;
    vec2 uv3 = uv0;

    uv1.y += -gap + yoffset;
    uv2.y += yoffset;
    uv3.y += gap + yoffset;

    uv1.y = mod(uv1.y, gap * 2.) - gap;
    uv2.y = mod(uv2.y, gap * 2.) - gap;
    uv3.y = mod(uv3.y, gap * 2.) - gap;


    vec4 allblur1 = texture2D(_MainTex, uv1);
    vec4 allblur2 = texture2D(_MainTex, uv2);
    // vec4 allblur3 = texture2D(_MainTex, uv3);

    // allblur1 *= step(0., uv1.y) * step(uv1.y, 1.);
    // allblur2 *= step(0., uv2.y) * step(uv2.y, 1.);
    // allblur3 *= step(0., uv3.y) * step(uv3.y, 1.);

    // allblur1.rgb = vec3(0.);

    vec4 res = allblur1 + allblur2;

    gl_FragColor = res;
    // gl_FragColor = vec4(uv0, 0,1);
    gl_FragColor *= smoothstep(0., softmask+0.01, uv0.y) * smoothstep(1., 1.-softmask-0.01, uv0.y);
    // gl_FragColor *= smoothstep(0.-softmask, 0., uv0.y) * smoothstep(1.+softmask, 1., uv0.y);
}

// void main(void)
// {
//     uvy.y -= 0.5;
//     uvy.y *= 1./(1. - gap * 2.0);
//     uvy.y += .5;
//     uvy.y = fract(uvy.y + yoffset);
//     uvy.y = remap(gap, 1. - gap, uvy.y);
//     gl_FragColor = directionBlur(_MainTex, uvy, vec2(0., 1.), blurSize_all) * smoothstep(0.5, 0.3, abs(uv0.y - .5));
// }