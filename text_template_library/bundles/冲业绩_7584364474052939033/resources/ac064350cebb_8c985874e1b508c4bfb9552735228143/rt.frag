precision mediump float;
varying highp vec2 uv0;

uniform sampler2D _MainTex;
uniform vec3 param;


void main(void)
{
    vec4 color = texture2D(_MainTex, uv0);
    gl_FragColor = color;
}
