precision highp float;

uniform float u_OutputWidth;
uniform float u_OutputHeight;

uniform sampler2D _MainTex;
uniform vec3 param;
uniform vec2 blurDirection;
uniform float blurStep;
uniform float alpha;
uniform vec4 _MainTex_ST;
uniform float u_percent;
uniform float u_transition;

varying vec2 uv0;

#define BLUR_MOTION 0x1
#define BLUR_SCALE  0x2

#if defined(BLUR_TYPE) && BLUR_TYPE == BLUR_SCALE
#define num 25
#else
#define num 7
#endif

float random(in vec3 scale, in float seed) {
    /* use the fragment position for randomness */
    return fract(sin(dot(gl_FragCoord.xyz + seed, scale)) * 43758.5453 + seed);
}

vec4 directionBlur(sampler2D tex, vec2 resolution, vec2 uv, vec2 directionOfBlur, float intensity)
{
    vec2 pixelStep = 1.0/resolution * intensity;
    float dircLength = max(length(directionOfBlur), .000001);
	pixelStep.x = directionOfBlur.x * 1.0 / dircLength * pixelStep.x;
	pixelStep.y = directionOfBlur.y * 1.0 / dircLength * pixelStep.y;

	vec4 color = vec4(0);
	for(int i = -num; i <= num; i++)
	{
        vec2 blurCoord = uv + pixelStep * float(i);
        // vec2 uvT = vec2(1.0 - abs(abs(blurCoord.x) - 1.0), 1.0 - abs(abs(blurCoord.y) - 1.0));
#if defined(ANIMSEQ) && ANIMSEQ == 1
        blurCoord.x = clamp(blurCoord.x, 0., 1.);
        blurCoord.y = clamp(blurCoord.y, 0., 1.);
        blurCoord = blurCoord * _MainTex_ST.xy + _MainTex_ST.zw;
#endif
        color += texture2D(tex, blurCoord);
	}
	color /= float(2 * num + 1);	
	return color;
}

vec4 scaleBlur(vec2 uv) {
    vec4 color = vec4(0.0);
    float total = 0.0;
	vec2 toCenter = vec2(0.5, 0.5) - uv;
    float dissolve = 0.5;
    /* randomize the lookup values to hide the fixed number of samples */
    float offset3 = random(vec3(12.9898, 78.233, 151.7182), 0.0);

    for (int t = 0; t <= num; t++) {
        float percent = (float(t) + offset3 - .5) / float(num);
        float weight = 4.0 * (percent - percent * percent);

		vec2 curUV = uv + toCenter * percent * blurStep;
        // vec2 uvT = vec2(1.0 - abs(abs(curUV.x) - 1.0), 1.0 - abs(abs(curUV.y) - 1.0));

#if defined(ANIMSEQ) && ANIMSEQ == 1
        curUV.x = clamp(curUV.x, 0., 1.);
        curUV.y = clamp(curUV.y, 0., 1.);
        curUV = curUV * _MainTex_ST.xy + _MainTex_ST.zw;
#endif
        color += texture2D(_MainTex, curUV) * weight;
        // color += crossFade(uvT + toCenter * percent * blurStep, dissolve) * weight;
        total += weight;
    }
    return color / total;
}

float calAlpha(float percent, float transition, vec2 uvInput, int angle, int appear){
    float result = 1.0;

    vec2 range = vec2(percent * (1.0 + transition) - transition * 0.5);
    range.x = range.x - transition * 0.5;
    range.y = range.y + transition * 0.5;

    vec2 alphaRange = vec2(0.0);
    if(appear == 1){ // disappear
        alphaRange.x = 1.0;
    }else{ // appear
        alphaRange.y = 1.0;
    }
    float pos = 0.0;
    if (angle == 0){ // left->right
        pos = uvInput.x;
    }else if(angle == 1){ // right <- left
        pos = 1.0 - uvInput.x;
    }else if(angle == 2){ // top -> bottom
        pos = uvInput.y;
    }else if(angle == 3){// bottom -> top
        pos = 1.0 - uvInput.y;
    }

    if(pos < range.x){
        result = alphaRange.x;
    }else if(pos < range.y){
        if(appear == 1){
            result = 1.0 - (pos - range.x) / transition;
        }else{
            result = (pos - range.x) / transition;
        }
        result = smoothstep(0.0, 1.0, result);
    }else{
        result = alphaRange.y;
    }
    return result;
}

void main()
{
    vec4 color = vec4(0);
    vec2 uvF = vec2(uv0);
    #if defined(BLUR_TYPE) && BLUR_TYPE == BLUR_MOTION
    color = directionBlur(_MainTex, vec2(u_OutputWidth, u_OutputHeight), uvF, blurDirection, blurStep);
    #elif defined(BLUR_TYPE) && BLUR_TYPE == BLUR_SCALE
    color = scaleBlur(uvF);
    #else
    uvF = vec2(uv0);

    #if defined(ANIMSEQ) && ANIMSEQ == 1
    uvF.x = clamp(uvF.x, 0., 1.);
    uvF.y = clamp(uvF.y, 0., 1.);
    uvF = uvF * _MainTex_ST.xy + _MainTex_ST.zw;
    #endif
    color = texture2D(_MainTex, uvF);
    #endif
    color *= calAlpha(u_percent, u_transition, uv0, 1, 1);
    gl_FragColor = color;
}
