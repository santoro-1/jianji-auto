precision highp float;
varying highp vec2 uv0;
uniform sampler2D _MainTex;
uniform sampler2D noiseTexture;

uniform float _time;
uniform float flag;
uniform float blurSize;
uniform highp vec4 texSize;



float uvProtect(vec2 samplerTexCoord)
{
    return step(0.,samplerTexCoord.x)*step(0.,samplerTexCoord.y)*step(samplerTexCoord.x,1.0)*step(samplerTexCoord.y,1.0);
}
float texLightFlag(float samplerTexCoord,float t){
    float width = 0.25;
    float mid = 1.2*t;
    float d = smoothstep(mid-width,mid,1.0-samplerTexCoord)*smoothstep(mid+width,mid,1.0-samplerTexCoord);
    return (1.+0.5*d)*(smoothstep(t+0.1,t,1.0-samplerTexCoord));
}
float lightMask(float samplerTexCoord,float t){
    float d=1.0;
    float mid=t-0.02;
    float width = 0.1;
    d = smoothstep(mid+width,mid,1.0-samplerTexCoord);
    float d2 = smoothstep(mid-0.3-width,mid-0.3,1.0-samplerTexCoord);
    float flag=1.0-step(0.85,t)*(t-0.85)/0.15;
    return d*d2*flag*3.0;
}
float n21(vec2 p){
    return fract(sin(p.x*100.+p.y*168.)*2368.)*0.25+0.75;
}
void main()
{
    vec2 uv = uv0;
    uv=(uv-0.5)*2.+0.5;
    
    vec4 result = texture2D(_MainTex, uv);
    vec2 myTexSize = texSize.xy;
    
    float axis = mix(1.0-uv.x,uv.y,flag);
    // if(texSize.x>texSize.y)
    //     axis = 1.0-uv.x;
    vec4 oriCol = result*texLightFlag(axis,_time);
    result*=lightMask(axis,_time);
    float sum = 1.0;
    
    
    
    float yOffset=1.3-1.2*_time-0.0*(0.5-clamp(axis,0.0,1.0));
    yOffset=yOffset;
    vec2 centerOffset= mix(vec2(1.0-yOffset,0.5),vec2(0.5,yOffset),flag);
    vec2 offset = uv-centerOffset;
    float flag1;
    float flag2;
    if(flag>0.5){
        flag1=step(offset.y,-0.1);
        flag2=step(0.1,offset.y);
        offset.y=(offset.y+0.01667*flag1-0.01667*flag2)/mix(1.2,1.0,flag1+flag2);
    }
    else
    {
        flag1=step(offset.x,-0.1);
        flag2=step(0.1,offset.x);
        offset.x=(offset.x+0.01667*flag1-0.01667*flag2)/mix(1.2,1.0,flag1+flag2);
    }

    
    vec2 normolizeUV=uv;
    vec2 normalOffset;
    float flag3;
    float flag4;
    float ratioFlag=min(myTexSize.x,myTexSize.y)/max(myTexSize.x,myTexSize.y);
    if(flag>0.5){
        normolizeUV.x=(normolizeUV.x-0.5)*ratioFlag+0.5;
        normalOffset = normolizeUV-centerOffset;
        flag3=step(normalOffset.y,-0.1);
        flag4=step(0.1,normalOffset.y);
        normalOffset.y=(normalOffset.y+0.01667*flag3-0.01667*flag4)/mix(1.2,1.0,flag3+flag4);
    }
    else{
        normolizeUV.y=(normolizeUV.y-0.5)*ratioFlag+0.5;
        normalOffset = normolizeUV-centerOffset;
        flag3=step(normalOffset.x,-0.1);
        flag4=step(0.1,normalOffset.x);
        normalOffset.x=(normalOffset.x+0.01667*flag3-0.01667*flag4)/mix(1.2,1.0,flag3+flag4);
    }

    float angleFlag=(length(normalOffset)+0.6*length(offset))/length(normalOffset);

    if(length(offset)>0.35)
        offset=normalize(offset)*0.35;

   
    vec2 blurOffset = blurSize*offset/vec2(100.)*angleFlag*ratioFlag;
    float blurStep = 64.-step(_time,0.1)*(0.1-_time)/0.1*32.;
    for(float j=1.0 ; j < 64. ; j+= 1.0)
    {
        float intensity=mix(1.,0.75,(j-1.)/64.)/j;
        vec2 samplerTexCoord = vec2(uv.x , uv.y)- j*blurOffset;
        float uvPro = intensity;
        float axis2 = mix(1.0-samplerTexCoord.x,samplerTexCoord.y,flag);
        vec4 tc = texture2D(_MainTex, samplerTexCoord)*texLightFlag(axis2,_time)*lightMask(axis2,_time);
        result += tc*uvPro;
        sum += 1.0*uvPro;
        if(j>blurStep)
             break;

    }
    result/=(sum);
    gl_FragColor =result;
}