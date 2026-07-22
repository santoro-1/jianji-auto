precision lowp float;
varying highp vec2 uv0;
uniform sampler2D _MainTex;
uniform sampler2D u_albedo;
uniform vec2 u_TextRect;
uniform float u_Offset;
uniform float u_Flag;
uniform float u_Angle;

void main()
{
    gl_FragColor = texture2D(_MainTex, uv0) ;
}
