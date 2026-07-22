precision lowp float;
varying vec4 chcolor;
varying vec4 dis_grad;
varying vec4 tex_ktv;
varying vec4 char1;
varying vec2 ktv_angle;
varying float smoothing_fwidth;

uniform highp sampler2D _MainTex;
#ifdef _TEXTURE
uniform sampler2D _Diffuse;
#endif

uniform vec4 _Color1;
uniform vec4 _Color1_2;
uniform vec4 _Color2;
uniform vec4 _Color2_3;
uniform vec4 _Color3;
uniform vec4 _ControlPercent;
uniform vec4 _ColorPercent;
uniform vec4 _AngleVec;
uniform vec4 _Scale2_Smoothing_AnimAlpha;
uniform vec2 _ShadowScale;
uniform float _ExtraSmoothing;
uniform vec4 u_Time;
uniform float t;
varying vec4 WH;
const highp float oneConst = 1.0;
const highp float halfConst = 0.5;
const highp float zeroConst = 0.0;
const highp vec2 bitSh16 = vec2(256., 1.);
const highp vec2 bitMsk16 = vec2(0., 1. / 256.);
const highp vec2 bitShifts16 = vec2(1.) / bitSh16;
highp float unpack16(highp vec2 color) { return dot(color, bitShifts16); }

/* discontinuous pseudorandom uniformly distributed in [-0.5, +0.5]^3 */
vec3 random3(vec3 c) {
	float j = 4096.0*sin(dot(c,vec3(17.0, 59.4, 15.0)));
	vec3 r;
	r.z = fract(512.0*j);
	j *= .125;
	r.x = fract(512.0*j);
	j *= .125;
	r.y = fract(512.0*j);
	return r-0.5;
}

/* skew constants for 3d simplex functions */
const float F3 =  0.3333333;
const float G3 =  0.1666667;

/* 3d simplex noise */
float simplex3d(vec3 p) {
	 /* 1. find current tetrahedron T and it's four vertices */
	 /* s, s+i1, s+i2, s+1.0 - absolute skewed (integer) coordinates of T vertices */
	 /* x, x1, x2, x3 - unskewed coordinates of p relative to each of T vertices*/
	 
	 /* calculate s and x */
	 vec3 s = floor(p + dot(p, vec3(F3)));
	 vec3 x = p - s + dot(s, vec3(G3));
	 
	 /* calculate i1 and i2 */
	 vec3 e = step(vec3(0.0), x - x.yzx);
	 vec3 i1 = e*(1.0 - e.zxy);
	 vec3 i2 = 1.0 - e.zxy*(1.0 - e);
	 	
	 /* x1, x2, x3 */
	 vec3 x1 = x - i1 + G3;
	 vec3 x2 = x - i2 + 2.0*G3;
	 vec3 x3 = x - 1.0 + 3.0*G3;
	 
	 /* 2. find four surflets and store them in d */
	 vec4 w, d;
	 
	 /* calculate surflet weights */
	 w.x = dot(x, x);
	 w.y = dot(x1, x1);
	 w.z = dot(x2, x2);
	 w.w = dot(x3, x3);
	 
	 /* w fades from 0.6 at the center of the surflet to 0.0 at the margin */
	 w = max(0.6 - w, 0.0);
	 
	 /* calculate surflet components */
	 d.x = dot(random3(s), x);
	 d.y = dot(random3(s + i1), x1);
	 d.z = dot(random3(s + i2), x2);
	 d.w = dot(random3(s + 1.0), x3);
	 
	 /* multiply d by w^4 */
	 w *= w;
	 w *= w;
	 d *= w;
	 
	 /* 3. return the sum of the four surflets */
	 return dot(d, vec4(52.0));
}

float noise(vec3 m) {
    return   0.5333333*simplex3d(m)
			+0.2666667*simplex3d(2.0*m)
			+0.1333333*simplex3d(4.0*m)
			+0.0666667*simplex3d(8.0*m);
}

float linearstep(float edge0, float edge1, float x) {
  float t = (x - edge0) / (edge1 - edge0);
  return clamp(t, 0.0, 1.0);
}

void main()
{
    //float extraSmoothing = 0.005;
    float scale2_Smoothing_AnimAlpha_x = _Scale2_Smoothing_AnimAlpha.x;
    float scale2_Smoothing_AnimAlpha_y = _Scale2_Smoothing_AnimAlpha.y;
    // gradient color
    float smoothing = _Scale2_Smoothing_AnimAlpha.z + smoothing_fwidth;
    vec4 cc = _Color1;
    float x = zeroConst;
#ifdef _COLOR2
    float gradDist = ((dis_grad.z - halfConst) * _AngleVec.r + (dis_grad.w - halfConst) * _AngleVec.g)/_AngleVec.b + halfConst;
#ifdef _LINEAR
    x = clamp(gradDist, _ColorPercent.x, _ControlPercent.x);
    x = (x - _ColorPercent.x)/(_ControlPercent.x - _ColorPercent.x);
    cc = mix(cc, _Color1_2, x);

    x = clamp(gradDist, _ControlPercent.x, _ColorPercent.y);
    x = (x - _ControlPercent.x)/(_ColorPercent.y - _ControlPercent.x);
    cc = mix(cc, _Color2, x);
#else
    x = linearstep(_ControlPercent.x - halfConst * smoothing, _ControlPercent.x + halfConst * smoothing, gradDist);
    cc = mix(cc, _Color2, x);
#endif

#ifdef _COLOR3
#ifdef _LINEAR
    x = clamp(gradDist, _ColorPercent.y, _ControlPercent.y);
    x = (x - _ColorPercent.y) / (_ControlPercent.y - _ColorPercent.y);
    cc = mix(cc, _Color2_3, x);

    x = clamp(gradDist, _ControlPercent.y, _ColorPercent.z);
    x = (x - _ControlPercent.y) / (_ColorPercent.z - _ControlPercent.y);
    cc = mix(cc, _Color3, x);
#else
    x = linearstep(_ControlPercent.y - 0.4 * smoothing, _ControlPercent.y + 0.4 * smoothing, gradDist);
    cc = mix(cc, _Color3, x);
#endif
#endif
#endif

#ifdef _TEXTURE
    vec4 diff = texture2D(_Diffuse, vec2(tex_ktv.x, oneConst - tex_ktv.y)) * _Scale2_Smoothing_AnimAlpha.w;
    cc = cc * (1.0 - diff.a) + diff;
#endif
    vec2 uvN = dis_grad.zw * 4.0 - 2.0;
    float offx = noise(vec3(uvN.xy * 2.0 + vec2(u_Time.x * 8.0, 0.0) + (WH.xy - WH.zw) * 100.0, u_Time.y * 4.0) + 12.0);
    float offy = noise(vec3((1. - uvN.yx) * 2.0 + vec2(0.0, u_Time.x * 8.0) - (WH.xy - WH.zw) * 100.0, u_Time.y * 4.0) - 12.0);
    vec2 uvi = dis_grad.xy + vec2(offx, offy) * 0.0025 / vec2(WH.xy - WH.zw);
    highp vec4 dis_tex = texture2D(_MainTex, uvi);
    highp float distance_smooth = unpack16(dis_tex.ba);
    highp float distance_clear = unpack16(dis_tex.rg);
    highp float ratio = smoothstep(zeroConst, 0.1, _Scale2_Smoothing_AnimAlpha.z);
    highp float distance = distance_clear*(oneConst-ratio) + distance_smooth*ratio;
    float alpha = oneConst;
    float l = clamp(oneConst - scale2_Smoothing_AnimAlpha_x - smoothing, zeroConst, oneConst);
    alpha *= oneConst - linearstep(l, oneConst - scale2_Smoothing_AnimAlpha_x + smoothing, distance);
    l = clamp(oneConst - scale2_Smoothing_AnimAlpha_y - smoothing, zeroConst, oneConst);
    alpha *= linearstep(l, oneConst - scale2_Smoothing_AnimAlpha_y + smoothing, distance);


    dis_tex = texture2D(_MainTex, dis_grad.xy);
    distance_smooth = unpack16(dis_tex.ba);
    distance_clear = unpack16(dis_tex.rg);
    ratio = smoothstep(zeroConst, 0.1, _Scale2_Smoothing_AnimAlpha.z);
    distance = distance_clear*(oneConst-ratio) + distance_smooth*ratio;
    
    float alpha1 = oneConst;
    l = clamp(oneConst - scale2_Smoothing_AnimAlpha_x - smoothing, zeroConst, oneConst);
    alpha1 *= oneConst - linearstep(l, oneConst - scale2_Smoothing_AnimAlpha_x + smoothing, distance);
    l = clamp(oneConst - scale2_Smoothing_AnimAlpha_y - smoothing, zeroConst, oneConst);
    alpha1 *= linearstep(l, oneConst - scale2_Smoothing_AnimAlpha_y + smoothing, distance);

    alpha = alpha1 + alpha * (1. - alpha1);
    cc *= chcolor;
#ifdef _INNER_SHADOW
    float inner_dis = unpack16(texture2D(_MainTex, dis_grad.xy + _ShadowScale).rg);
    float inner_alpha = linearstep(halfConst - smoothing, halfConst + smoothing, inner_dis);
    alpha *= inner_alpha;
#endif

#ifndef KTV_DISABLE
    float ktvDist = dis_grad.z * ktv_angle.x + dis_grad.w * ktv_angle.y;
    float alpha_less = step(tex_ktv.w, zeroConst);
    float alpha_greater = oneConst - alpha_less;
    float ktv_right = step(ktvDist, tex_ktv.z);
    float ktv_alpha = (oneConst - ktv_right) * alpha_less + ktv_right * alpha_greater;
    alpha *= ktv_alpha;
#endif
    gl_FragColor = vec4(cc.rgb * alpha * cc.a, cc.a * alpha);
    gl_FragColor = vec4(alpha * cc);
    vec2 uvdis = dis_grad.zw * 2.0 - 1.0;
    vec2 mm = ((WH.xy - WH.zw));
    vec3 p3 = vec3(uvdis, t*2.4*(mm.x + mm.y));    
        
    float intensity = noise(vec3(p3*4.0+12.0));
    // float t = clamp((uvdis.x * -uvdis.x * 0.16) + 0.15, 0., 1.);                         
    float y = abs(intensity * 0.2 + distance - 0.47);
        
    float g = pow(y, 0.18);
                            
    vec3 col = vec3(0.5, 1.78, 0.9);
    float m = 1.78 - g * 1.78;
    m *= m;
    m *= m;
    // col = col * -g + col;                    
    // col = col * col;
    // col = col * col;
    m = alpha1 + m * (1. - alpha1);
    gl_FragColor = cc * m;
    // gl_FragColor = vec4(t);
    // gl_FragColor = char1.zwxy;
    // gl_FragColor = dis_tex;
    // gl_FragColor = _Scale2_Smoothing_AnimAlpha * _Color1.r;
    // gl_FragColor = _Scale2_Smoothing_AnimAlpha;
    // gl_FragColor = dis_tex;
    // gl_FragColor.rg = dis_grad.zw;
    // gl_FragColor.ba = vec2(alpha, 1.0);

}
