precision highp float;
varying highp vec2 uv0;
uniform sampler2D _MainTex;

uniform float progress;
uniform float blurStep;

uniform vec2 u_ScreenParams;

const int num = 25;

uniform float fade;

uniform vec2 trapezoid;

float random(in vec3 scale, in float seed) {
    /* use the fragment position for randomness */
    return fract(sin(dot(gl_FragCoord.xyz + seed, scale)) * 43758.5453 + seed);
}

vec4 directionBlur(sampler2D tex, vec2 uv, vec2 directionOfBlur, float intensity)
{
    vec2 pixelStep = 1.0/u_ScreenParams * intensity;
    float dircLength = max(length(directionOfBlur), .000001);
	pixelStep.x = directionOfBlur.x * 1.0 / dircLength * pixelStep.x;
	pixelStep.y = directionOfBlur.y * 1.0 / dircLength * pixelStep.y;

	vec4 color = vec4(0);
	for(int i = -num; i <= num; i++)
	{
        vec2 blurCoord = uv + pixelStep * float(i);
        // vec2 uvT = vec2(1.0 - abs(abs(blurCoord.x) - 1.0), 1.0 - abs(abs(blurCoord.y) - 1.0));
        blurCoord.x = clamp(blurCoord.x, 0., 1.);
        blurCoord.y = clamp(blurCoord.y, 0., 1.);
        // blurCoord = blurCoord * _MainTex_ST.xy + _MainTex_ST.zw;
        color += texture2D(tex, blurCoord);
	}
	color /= float(2 * num + 1);	
	return color;
}

vec4 scaleBlur(vec2 uv) {
    vec4 color = vec4(0.0);
    float total = 0.0;
	vec2 toCenter = vec2(1.5, 0.5) - uv;
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
        color += texture2D(_MainTex, curUV) * weight;
        total += weight;
    }
    return color / total;
}

float cross(vec2 a , vec2 b) { return a.x*b.y - a.y*b.x; }
vec2 invBilinear(vec2 p,  vec2 a,  vec2 b,  vec2 c,  vec2 d)
{
    vec2 res = vec2(-1.0);

    vec2 e = b-a;
    vec2 f = d-a;
    vec2 g = a-b+c-d;
    vec2 h = p-a;
        
    float k2 = cross( g, f );
    float k1 = cross( e, f ) + cross( h, g );
    float k0 = cross( h, e );
    
    // if edges are parallel, this is a linear equation
    if( abs(k2)<0.001 )
    {
        res = vec2( (h.x*k1+f.x*k0)/(e.x*k1-g.x*k0), -k0/k1 );
    }
    // otherwise, it's a quadratic
    else
    {
        float w = k1*k1 - 4.0*k0*k2;
        if( w<0.0 ) return vec2(-1.0);
        w = sqrt( w );

        float ik2 = 0.5/k2;
        float v = (-k1 - w)*ik2;
        float u = (h.x - f.x*v)/(e.x + g.x*v);
        
        if( u<0.0 || u>1.0 || v<0.0 || v>1.0 )
        {
           v = (-k1 + w)*ik2;
           u = (h.x - f.x*v)/(e.x + g.x*v);
        }
        res = vec2( u, v );
    }
    res.y = 1.0 - res.y;
    return res;
}

void main(void)
{
    // vec4 resCol = texture2D(_MainTex, uv0);
    vec2 uv1 = uv0;
    uv1 = invBilinear(uv1, vec2(0., 1.+trapezoid.x), vec2(1., 1.+trapezoid.y), vec2(1., -trapezoid.y), vec2(0., 0.-trapezoid.x));
    gl_FragColor = scaleBlur(uv1);
    gl_FragColor *= smoothstep(0., 0.01 + fade, uv1.x) * smoothstep(1., 0.99 - fade, uv1.x);
    // gl_FragColor *= step(0., uv1.y) * step(uv1.y, 1.);
}