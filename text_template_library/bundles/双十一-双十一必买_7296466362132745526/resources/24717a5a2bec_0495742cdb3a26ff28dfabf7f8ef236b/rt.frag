precision highp float;

varying vec2 fTexCoord;
uniform sampler2D _MainTex;
uniform sampler2D u_colorTexture;
uniform sampler2D u_blackTexture;
uniform vec4 u_ScreenParams;
uniform float u_blackRange;
uniform  float u_blackSmoothRange;
uniform  vec4 u_colorChange;
uniform float u_uvOffset;
uniform float u_minAlpha;
uniform float u_distort;
uniform float u_angle;
uniform float u_colorV;
uniform float u_lineScale;

const highp vec2 c_direction = vec2(-1,-1);
const float PI = 3.1415926;
const float c_strength = 0.4;
const float c_smoothRange = 0.9;
const vec3 c_newColor = vec3(255,255,229)/255.;

void main() 
{
    
    highp vec2 inputUv = vec2(fTexCoord.x, 1.-fTexCoord.y);
    vec4 inputColor = texture2D(_MainTex,inputUv);
    highp vec2 ratio = u_ScreenParams.xy/max(u_ScreenParams.x,u_ScreenParams.y);

    highp vec2 uv = (fTexCoord-0.5);
    float theta = u_angle * PI / 180.0;
    uv = uv * mat2(cos(theta), -(u_ScreenParams.x / u_ScreenParams.y) * sin(theta), (u_ScreenParams.y / u_ScreenParams.x) * sin(theta), cos(theta));
    float uvScale =  1200. / 1600. * 0.8 * max(ratio.x,ratio.y) * u_lineScale;
    uv = (uv) * uvScale + 0.5;
    highp vec2 uvOffset = u_uvOffset * (c_direction) ;//* normalize(vec2(tan(theta-PI/2.),-1));
    float uvOffsetScale = -u_uvOffset;
    uv = uv + uvOffset*uvScale;
    vec3 c_lineP = vec3(tan(theta+PI/4.),-1,0);


    c_lineP.z = (uvOffsetScale * sign(sin(theta+PI/4.))-0.5)*(c_lineP.x)+0.5+uvOffsetScale * sign(cos(theta+PI/4.));
    float dist = abs(dot(c_lineP.xy, inputUv)+c_lineP.z)/sqrt(dot(c_lineP.xy,c_lineP.xy));
    float blackMask = 1. - smoothstep(u_blackRange-u_blackSmoothRange, u_blackRange, dist);
    vec4 resultColor = inputColor;
    vec4 newColor = vec4(c_newColor,1.) * ((1.-smoothstep(u_blackRange, u_blackRange+c_smoothRange, dist)) * c_strength + 1. );
    resultColor = mix(inputColor, newColor * inputColor.a, (blackMask*(1.-u_minAlpha)+u_minAlpha));
    gl_FragColor.rgb = resultColor.rgb;
    gl_FragColor.a = inputColor.a;
    // gl_FragColor = vec4(1,0,0,1);
}