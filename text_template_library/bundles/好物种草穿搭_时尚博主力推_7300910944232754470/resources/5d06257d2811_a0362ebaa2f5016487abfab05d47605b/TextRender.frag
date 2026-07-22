precision highp float;
varying highp vec2 uv0;
uniform sampler2D u_albedo;
uniform float u_Intensity;
uniform float u_Scale;
uniform float u_Line;
uniform sampler2D _MainTex;
uniform float u_Flag;
const float PI = 3.1415926;
void main()
{
    float flag = step(0.5, u_Flag);
    float x = mix(uv0.x, uv0.y, flag) - 0.5;
    float distor = pow(sqrt(0.25 - x * x) * 2.0, 1.5) * 0.5;
    vec2 d = mix(vec2(0.0, distor), vec2(distor, 0.0), flag);
    float y = max(mix(uv0.y, 1. - uv0.x, flag) - u_Line, 0.0) * -(flag * 2.0 - 1.0);
    vec2 uv = uv0 - d * y * u_Intensity;
    uv = mix(
        vec2(uv.x, uv.y * u_Scale),
        vec2(1. - (1. - uv.x) * u_Scale, uv.y),
        flag
    );
    gl_FragColor = texture2D(_MainTex, uv);
}
