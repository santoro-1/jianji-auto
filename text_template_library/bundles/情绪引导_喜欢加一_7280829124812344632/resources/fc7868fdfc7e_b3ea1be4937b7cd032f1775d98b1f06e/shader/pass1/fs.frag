precision highp float;
varying vec2 uv0;
uniform sampler2D _MainTex;
uniform float u_alhpa1;
uniform float u_alhpa2;
uniform float u_alhpa3;
uniform float u_alhpa4;
uniform vec2 u_pos1;
uniform vec2 u_pos2;
uniform vec2 u_pos3;
uniform vec2 u_pos4;
uniform vec2 u_maxPos;
void main()
{
	vec2 uv1 = uv0;
	vec4 diffuse = texture2D(_MainTex, uv1+u_pos1/u_maxPos)*u_alhpa1;
	vec4 color1 = texture2D(_MainTex, uv1+u_pos2/u_maxPos)*u_alhpa2;
	diffuse = mix(diffuse, color1, color1.a);
	diffuse = mix(diffuse, color1, color1.a);
	color1 = texture2D(_MainTex, uv1+u_pos3/u_maxPos)*u_alhpa3;
	diffuse = mix(diffuse, color1, color1.a);
	color1 = texture2D(_MainTex, uv1+u_pos4/u_maxPos)*u_alhpa4;
	diffuse = mix(diffuse, color1, color1.a);
	gl_FragColor = diffuse;
}