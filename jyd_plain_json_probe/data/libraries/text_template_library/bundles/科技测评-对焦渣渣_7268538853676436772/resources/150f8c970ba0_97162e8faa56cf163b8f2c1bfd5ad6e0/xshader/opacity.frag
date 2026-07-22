precision highp float;
precision highp int;

uniform sampler2D _MainTex;
uniform float blurStep;
uniform vec2 direction;
uniform vec2 screenSize;
//uniform float u_opacity;
const int num = 25;

varying vec2 v_uv;

vec4 directionBlur(sampler2D tex, vec2 uv, vec2 directionOfBlur, float intensity)
{
    vec2 pixelStep = vec2(1.0) / screenSize * vec2(intensity);
//    vec2 pixelStep = 1.0/u_ScreenParams * intensity;
    float dircLength = max(length(directionOfBlur), .000001);
	pixelStep.x = directionOfBlur.x * 1.0 / dircLength * pixelStep.x;
	pixelStep.y = directionOfBlur.y * 1.0 / dircLength * pixelStep.y;

	vec4 color = vec4(0);
	for(int i = -num; i <= num; i++)
	{
        vec2 blurCoord = uv + pixelStep * vec2(float(i));
        // vec2 uvT = vec2(1.0 - abs(abs(blurCoord.x) - 1.0), 1.0 - abs(abs(blurCoord.y) - 1.0));
        blurCoord.x = clamp(blurCoord.x, 0., 1.);
        blurCoord.y = clamp(blurCoord.y, 0., 1.);
        // blurCoord = blurCoord * _MainTex_ST.xy + _MainTex_ST.zw;
        color += texture2D(tex, blurCoord);
	}
	color /= float(2 * num + 1);
	return color;
}

void main() {
    gl_FragColor = directionBlur(_MainTex, v_uv, direction, blurStep);
//    gl_FragColor = texture2D(_MainTex, v_uv) * u_opacity;
}
