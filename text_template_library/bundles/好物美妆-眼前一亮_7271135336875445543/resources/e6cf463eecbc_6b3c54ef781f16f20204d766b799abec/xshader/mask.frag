precision lowp float;
varying highp vec2 uv0;
uniform sampler2D _MainTex;
uniform sampler2D u_albedo;
uniform vec2 u_TextRect;
uniform float u_Offset;
uniform float u_Flag;
uniform float u_Angle;
uniform float width;

uniform float lineCount;

uniform vec4 mask1;
uniform vec4 mask2;
uniform vec4 mask3;
uniform vec4 mask4;
uniform vec4 mask5;
uniform vec4 mask6;
uniform vec4 mask7;
uniform vec4 mask8;
uniform vec4 mask9;
uniform vec4 mask10;
uniform float typeSetting;
uniform float s_width;

void main()
{
    float solid_width = 0.1;
    float alpha = 0.;
    float step1 = 0.03;
    float multi_width = s_width;
    if(typeSetting > 0.5)
    {
        if(lineCount > 0.5)
        {
            step1 = abs(mask1.y- mask1.z)*0.2;
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.y - mask1.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.x - mask1.y)*smoothstep(step1,-step1,uv0.x - mask1.z);
            alpha = alpha +mask1.w*cur_alpha;
        }
        if (lineCount > 1.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.y - mask2.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.x - mask2.y)*smoothstep(step1,-step1,uv0.x - mask2.z);
            alpha = alpha +mask2.w*cur_alpha;
        }
        if (lineCount > 2.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask3.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask3.y)*smoothstep(step1,-step1,uv0.y - mask3.z);
            alpha = alpha +mask3.w*cur_alpha;
        }
        if (lineCount > 3.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.y - mask4.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.x - mask4.y)*smoothstep(step1,-step1,uv0.x - mask4.z);
            alpha = alpha +mask4.w*cur_alpha;
        }
        if (lineCount > 4.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask5.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask5.y)*smoothstep(step1,-step1,uv0.y - mask5.z);
            alpha = alpha +mask5.w*cur_alpha;
        }
        if (lineCount > 5.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask6.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask6.y)*smoothstep(step1,-step1,uv0.y - mask6.z);
            alpha = alpha +mask6.w*cur_alpha;
        }
        if (lineCount > 6.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask7.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask7.y)*smoothstep(step1,-step1,uv0.y - mask7.z);
            alpha = alpha +mask7.w*cur_alpha;
        }
        if (lineCount > 7.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask8.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask8.y)*smoothstep(step1,-step1,uv0.y - mask8.z);
            alpha = alpha +mask8.w*cur_alpha;
        }
    }else{
        if(lineCount > 0.5)
        {
            step1 = abs(mask1.y- mask1.z)*0.2;
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask1.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask1.y)*smoothstep(step1,-step1,uv0.y - mask1.z);
            alpha = alpha +mask1.w*cur_alpha;
        }
        if (lineCount > 1.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask2.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask2.y)*smoothstep(step1,-step1,uv0.y - mask2.z);
            alpha = alpha +mask2.w*cur_alpha;
        }
        if (lineCount > 2.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask3.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask3.y)*smoothstep(step1,-step1,uv0.y - mask3.z);
            alpha = alpha +mask3.w*cur_alpha;
        }
        if (lineCount > 3.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask4.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask4.y)*smoothstep(step1,-step1,uv0.y - mask4.z);
            alpha = alpha +mask4.w*cur_alpha;
        }
        if (lineCount > 4.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask5.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask5.y)*smoothstep(step1,-step1,uv0.y - mask5.z);
            alpha = alpha +mask5.w*cur_alpha;
        }
        if (lineCount > 5.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask6.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask6.y)*smoothstep(step1,-step1,uv0.y - mask6.z);
            alpha = alpha +mask6.w*cur_alpha;
        }
        if (lineCount > 6.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask7.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask7.y)*smoothstep(step1,-step1,uv0.y - mask7.z);
            alpha = alpha +mask7.w*cur_alpha;
        }
        if (lineCount > 7.5)
        {
            float cur_alpha = smoothstep(width,width*multi_width,abs(uv0.x - mask8.x));
            cur_alpha = (1.0-cur_alpha)*smoothstep(-step1,step1,uv0.y - mask8.y)*smoothstep(step1,-step1,uv0.y - mask8.z);
            alpha = alpha +mask8.w*cur_alpha;
        }
    }

    gl_FragColor = vec4(alpha) ;
}
