precision mediump float;
varying highp vec2 uv0;

uniform sampler2D _MainTex;
uniform vec2 eraseUV;

void main(void) {
    vec4 color = texture2D(_MainTex, uv0);
    vec2 uv = uv0 * 2.0 - vec2(1.0);

    // float r = uv.x * uv.x / (eraseUV.x * eraseUV.x) + uv.y * uv.y / (eraseUV.y * eraseUV.y);
    float r = abs(uv.x) - eraseUV.x;
    float a = 1.0 - smoothstep(-0.4, 0.0, r);
    color *= a;
    gl_FragColor = color;
}
