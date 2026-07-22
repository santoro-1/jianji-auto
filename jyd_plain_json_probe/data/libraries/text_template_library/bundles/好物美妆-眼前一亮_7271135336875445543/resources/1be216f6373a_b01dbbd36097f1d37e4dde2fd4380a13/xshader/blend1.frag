precision highp float;
varying highp vec2 uv0;
uniform sampler2D inputTexture3;
uniform sampler2D inputTexture4;
uniform sampler2D maskTexture;
uniform sampler2D inputTexture6;

void main()
{
    vec4 orgColor = texture2D(inputTexture4,uv0);
    vec4 blurColor = texture2D(inputTexture3,uv0);
    vec4 maskColor = texture2D(inputTexture6,uv0);
    vec4 blend1 = mix(orgColor,blurColor,maskColor);

    // vec4 maskColor1 = texture2D(inputTexture6,vec2(uv0.x,uv0.y + 0.1));
    gl_FragColor = orgColor + blend1*(1.0-orgColor.a);
    // gl_FragColor = gl_FragColor + maskColor;
    // gl_FragColor = blend1 + maskColor1;
}
