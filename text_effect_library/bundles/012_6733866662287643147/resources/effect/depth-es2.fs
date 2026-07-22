precision highp float;
varying vec2 uv0;
uniform sampler2D _MainTex;
void main()
{
    gl_FragColor = vec4(0.0, 0.0, 0.0, 0.0);
    gl_FragDepth = 1.0;
}