
precision highp float;
varying vec2 uv0;
uniform sampler2D _MainTex;

void main()
{

    vec4 maincol1 = texture2D(_MainTex, uv0);
    gl_FragColor = maincol1  ;
}

