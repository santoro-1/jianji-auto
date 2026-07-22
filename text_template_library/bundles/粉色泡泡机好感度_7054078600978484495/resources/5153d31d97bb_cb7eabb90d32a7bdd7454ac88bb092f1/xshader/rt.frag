precision highp float;

uniform sampler2D _MainTex;

uniform float u_alpha;
uniform float u_yOffset;

uniform float u_alpha1;
uniform float u_yOffset1;

uniform float u_alpha2;
uniform float u_yOffset2;

varying vec2 uv0;


void main(){
    vec4 color = texture2D(_MainTex, vec2(uv0.x , uv0.y - u_yOffset));
    vec4 color1 = texture2D(_MainTex, vec2(uv0.x , uv0.y - u_yOffset1));
    vec4 color2 = texture2D(_MainTex, vec2(uv0.x , uv0.y - u_yOffset2));


    float overlap=color.a+color1.a+color2.a;
    overlap=step(1.1,overlap);
    
    color *=u_alpha;
    color1 *=u_alpha1;
    color2 *=u_alpha2;
    
    vec4 result=vec4(0.);
    if(overlap>.1){
        result=mix(color,color1,color1.a);
        result=mix(result,color2,color2.a);
    }
    else{
        result=clamp(color+color1+color2,0.,1.);
    }
    gl_FragColor=result;
}