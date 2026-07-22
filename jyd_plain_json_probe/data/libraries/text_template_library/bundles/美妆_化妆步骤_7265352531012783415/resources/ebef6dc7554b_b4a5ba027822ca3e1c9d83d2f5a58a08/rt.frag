precision mediump float;
varying highp vec2 uv0;

uniform sampler2D _MainTex;
uniform vec2 eraseUV;

void main(void)
{
    if (uv0.x > eraseUV.x)
    {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 0.0);
    }
    else
    {
        gl_FragColor = texture2D(_MainTex, uv0);
    }
}
