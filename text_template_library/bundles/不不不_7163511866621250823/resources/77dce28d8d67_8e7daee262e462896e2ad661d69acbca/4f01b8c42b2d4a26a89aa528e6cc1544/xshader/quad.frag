precision highp float;
varying highp vec2 uv0;
uniform sampler2D u_albedo;
uniform sampler2D _MainTex;
uniform vec4 u_ScreenParams;
uniform vec2 u_TextRect;
varying float v_Strength;
uniform float u_Strength1;
uniform vec2 u_Center;
uniform float u_Alpha;
uniform float u_TrailAlpha;
uniform float u_Offset;
uniform float u_RowNum;
uniform float u_cNum;
uniform vec4 u_Time;
uniform float u_Progress;
#define PI 3.1415926
#define SEED 1.123456789
#define HASHM mat3(40.15384,31.973157,31.179219,10.72341,13.123009,41.441023,-311.61923,10.41234,178.127121)

float remap01(float a, float b, float x)
{
    return (x - a) / (b - a);
}
float hash(vec3 p) {
	p = fract((vec3(p.x, p.y, p.z) + SEED * 1e-3) * HASHM);
    p += dot(p, p.yzx + 41.19);
    return fract((p.x + p.y) * p.z);
}
float hash31(vec3 p){
	vec3 p2 = fract((vec3(p.x, p.y, p.z) + SEED * 1e-6) * HASHM);
    p2+=dot(p2,p2.yzx+22.22);
    return fract((p2.x+p2.y)*p2.z);
}
float hash1(vec3 p) {
	vec3 p3 = fract(vec3(p.x, p.y, (p.z) + SEED * 1e-7) * HASHM);
    p3 += dot(p3, p3.yzx + 41.19);
//     float r = fract((p3.x + p3.y) * p3.z) * 2.0 - 1.0;
//    // return pow(r, 16.0) * sign(r) * 0.5 + 0.5;
//     r = r * step(0.8, abs(r));
//     r = remap01(0.8, 1.0, abs(r)) * sign(r) * 0.5 + 0.5;
//     return r;
    return fract((p3.x + p3.y) * p3.z);
}
float hash1(vec2 p) {
	vec3 p3 = fract(vec3(p.x, p.y, (p.x + p.y + SEED * 1e-7)) * HASHM);
    p3 += dot(p3, p3.yzx + 41.19);
    float r = fract((p3.x + p3.y) * p3.z);
    return r;
}


// float valueNoise(vec2 seed, vec2 fre)
// {
//     vec2 ise = floor(seed * fre);
//     vec2 fse = fract(seed * fre);
//     float thr = 0.0;
//     float minV = 1.0;
//     float r1 = min(max(hash(ise) - thr, 0.0), minV);
//     float r2 = min(max(hash(ise + vec2(1.0, 0.0)) - thr, 0.0), minV);
//     float r3 = min(max(hash(ise + vec2(0.0, 1.0)) - thr, 0.0), minV);
//     float r4 = min(max(hash(ise + vec2(1.0, 1.0)) - thr, 0.0), minV);
//     return mix(mix(r1, r2, fse.x), mix(r3, r4, fse.x), fse.y);
// }


// void main1()
// {   
//     float n = pow(valueNoise(vec2(uv0.x - 1.2, floor(u_Progress*8.0)), vec2(pow(u_cNum, 1.0) * 72.0, 1.0)), 1.0);
//     float n1 = valueNoise1(vec2(uv0.x - 1.2, floor(u_Progress*8.0)), vec2(pow(u_cNum, 1.0) * 32.0, 1.0));
//     // float n1 = pow(valueNoise(vec2(uv0.x + 10.0, u_Time.y), vec2(u_RowNum * 64.0, 1.0)), 1.0) * 2.0 - 1.0;
//     n = (n + n1 * 0.4) / 1.4;
//     n = clamp(n * 2.0 - 1.0, -0.5, 0.5);
//     vec2 uv = uv0 + vec2(0.0, n * (0.15*((cos(u_Progress*16.0*PI + PI))*0.5+0.5) / u_RowNum));
//     vec4 color1 = texture2D(_MainTex, uv);
//     gl_FragColor = vec4(color1);
// }

float valueNoise(vec3 seed, vec3 fre)
{
    vec3 ise = floor(seed * fre);
    vec3 fse = fract(seed * fre);
    float r1 = hash1(ise + vec3(0.0, 0.0, 0.0));
    float r2 = hash1(ise + vec3(1.0, 0.0, 0.0));
    float r3 = hash1(ise + vec3(0.0, 1.0, 0.0));
    float r4 = hash1(ise + vec3(0.0, 0.0, 1.0));
    float r5 = hash1(ise + vec3(1.0, 1.0, 0.0));
    float r6 = hash1(ise + vec3(1.0, 0.0, 1.0));
    float r7 = hash1(ise + vec3(0.0, 1.0, 1.0));
    float r8 = hash1(ise + vec3(1.0, 1.0, 1.0));
    fse = smoothstep(0.0, 1.0, fse);
    float n1 = mix(r1, r2, fse.x); 
    float n2 = mix(r3, r5, fse.x); 
    float n3 = mix(r4, r6, fse.x); 
    float n4 = mix(r7, r8, fse.x); 
    r1 = mix(n1, n2, 0.0);
    r2 = mix(n3, n4, 0.0);
    n1 = mix(r1, r2, fse.z);
    return n1;
}

float pnoise8(vec3 seed, vec3 fre, float persistence)
{
  float value = 0.0;
  float ampl = 1.0;
  float sum = 0.0;
  for(int i=0 ; i<6 ; i++)
  {
    sum += ampl;
    value += valueNoise(seed, fre) * ampl;
    fre *= vec3(2.0, 1.0, 1.0);
    ampl *= persistence;
  }
  return value / sum;
}

void main()
{
    float p = u_Progress;
    float n = pnoise8(vec3(uv0 + vec2(0.0, 0.2), p), vec3(1450.0 / 67.0 * u_cNum, 0.6, 4.0) + vec3(0, 0.2, 0), 0.5);
    n = clamp((n - 0.5) * 8.11 + 0.5, 0.0, 1.0);
    n = n * 2.0 - 1.0;//(0.03*((cos(u_Progress*4.0*PI + PI))*0.5+0.5)
    vec4 c1 = texture2D(_MainTex, vec2(uv0.x, uv0.y) + vec2(0.0, n * v_Strength / pow(u_RowNum, 0.8)));
    gl_FragColor = vec4(c1);
}
