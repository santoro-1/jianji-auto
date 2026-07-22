
precision highp float;
varying vec2 uv0;
uniform sampler2D _MainTex;

uniform vec4 u_ScreenParams;
uniform float bulge_height;
uniform float cone_radius;
uniform float alpha;

uniform vec2 bulge_radius;
uniform vec2 bulge_center;
uniform float pinning;
uniform vec2 u_TextRect;




void CornerPositioning(vec3 i_uv, out vec2 o_uv){
    o_uv = i_uv.xy/i_uv.z;
}

float cut(vec2 _u){ return step(0., _u.x) * step(_u.x, 1.) * step(0., _u.y) * step(_u.y, 1.); }

vec2 elliptical(vec2 p, float hradius, float vradius, vec2 center, float height) {
  vec2 d = abs(p - center);
  d = vec2(d.x / hradius, d.y / vradius);
  float dist = length(d);
  if (dist < 1.0) {
    float t = 1.0 - dist / height;
    vec2 offset = normalize(d) * t * height * 0.5;
    return p + offset;
  } else {
    return p;
  }
}

void BulgeEffect(vec2 i_uv, vec2 _radius, vec2 _center, float _height, float _taper_radius, float _pinning, vec2 screensize,
    out vec2 o_uv){
    vec2 uv1 = i_uv;
    // uv1 -= 0.5;
    uv1 -= _center;
    uv1 *= 2.;
    uv1 *= 1./_radius;
    float d = length(uv1);
    d = 1.-d;
    d = clamp(0., 1., d);

    // bulge uv
    vec2 uv2 = i_uv;
    uv2 -= 0.5;

    float cone = clamp(0., 1., _taper_radius);
    d = smoothstep(pow(cone, 2.)-0.001, pow(cone, 0.5)+0.001, d) * d;

    float pinning_mask = 1.;
    if(_pinning > 0.5){
        vec2 pinning_space = vec2(0.01*screensize.x/screensize.y, 0.01);
        pinning_mask = min(pinning_mask, smoothstep(pinning_space.x, pinning_space.x*5., uv0.x));
        pinning_mask = min(pinning_mask, smoothstep(1.-pinning_space.x, 1.-pinning_space.x*5., uv0.x));
        pinning_mask = min(pinning_mask, smoothstep(pinning_space.y, pinning_space.y*5., uv0.y));
        pinning_mask = min(pinning_mask, smoothstep(pinning_space.y, pinning_space.y*5., uv0.y));
    }

    float flip = mix(-1.,1.0,step(_center.y,0.0));
    o_uv = uv2;
 
    float fix_height = mix(screensize.y/screensize.x,1.0,step(screensize.x,screensize.y));
    o_uv += uv1*vec2(1.0,screensize.x/screensize.y/(9./16.)) * (2. - length(uv2))*mix(0., -_height*fix_height, pow(pinning_mask*d, 1.50));
    o_uv += 0.5;
}



void main()
{
    vec2 uv1 = uv0;

    vec2 o_uv=vec2(0); 
    BulgeEffect(uv1, bulge_radius, bulge_center, bulge_height, cone_radius, pinning, u_TextRect.xy, o_uv);

    float flag = (1.0-smoothstep(-0.00,0.10,abs(uv0.x -bulge_center.x)))*(1.0-smoothstep(-0.00,0.10,abs(uv0.y -bulge_center.y)));
    vec4 maincol1 = texture2D(_MainTex, o_uv)  ;
    gl_FragColor = maincol1 * alpha ;
    
}


// void main()
// {
//     gl_FragColor = texture2D(_MainTex, uv0) ;
// }
