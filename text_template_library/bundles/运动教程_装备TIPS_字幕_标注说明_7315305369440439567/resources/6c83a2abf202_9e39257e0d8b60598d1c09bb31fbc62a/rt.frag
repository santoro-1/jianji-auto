precision mediump float;
varying highp vec2 uv0;

uniform sampler2D _MainTex;

void main(void)
{
    gl_FragColor = texture2D(_MainTex, uv0);
}
