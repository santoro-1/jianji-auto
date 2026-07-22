precision highp float;

varying vec2 uv0;

uniform sampler2D _MainTex;
uniform float blur_progress;
uniform float typeSettingKind;
uniform vec2 text_size;
uniform vec2 cut_size;
uniform float backgroundEnabled;

void main()
{
    vec2 uv1 = uv0;
    vec4 res = texture2D(_MainTex, uv1);
    // if(typeSettingKind < 0.5)
    // {
    //     res *= smoothstep(mix(.98, 1.00001, blur_progress), mix(.95, 1., blur_progress), uv0.x);
    // }
    // else
    // {
    //     res *= smoothstep(mix(.98, 1.00001, blur_progress), mix(.95, 1., blur_progress), 1.-uv0.y);
    // }
    // if(backgroundEnabled > 0.5){
    //     if(typeSettingKind < 0.5)
    //     {
    //         res *= step(cut_size.x, uv0.x) * step(uv0.x, 1.-cut_size.x*0.5);
    //     }
    //     else
    //     {
    //         res *= step(cut_size.y, uv0.y) * step(uv0.y, 1.-cut_size.y);
    //     }
    // }
    // res = vec4(0,1,0,1);
    // res *= step(cut_size.x*0.5, uv0.x) * step(uv0.x, 1.-cut_size.x*0.5);
    // res *= step(cut_size.y*0.5, uv0.y) * step(uv0.y, 1.-cut_size.y*0.5);
    gl_FragColor = res;
}
