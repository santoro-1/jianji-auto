precision mediump float;
varying highp vec2 uv0;

uniform sampler2D _MainTex;
uniform vec3 param;

void main(void)
{
    float f = 1.5;  //频率
    float v = 3.0;  //速度
    float pi = 3.14159265359;
    vec2 uv;
    if (param.x < 0.1)
    {
        uv = vec2(uv0.x, uv0.y + param.z * sin(f * pi * uv0.x - 2.0 * pi * param.y));
    }
    else
    {
        uv = vec2(uv0.x + param.z * sin(f * pi * uv0.y + 2.0 * pi * param.y), uv0.y);
    }
    gl_FragColor = texture2D(_MainTex, uv);
}
