uniform vec4 uFinish;
out vec4 fragColor;
float heightAt(vec2 uv){return texture(sTD2DInputs[1],uv).g;}
void main(){
 vec2 uv=vUV.st,px=1.0/vec2(textureSize(sTD2DInputs[0],0));
 vec4 ink=texture(sTD2DInputs[0],uv),surface=texture(sTD2DInputs[1],uv);
 float h=surface.g;
 vec2 grad=vec2(heightAt(uv+vec2(px.x,0))-heightAt(uv-vec2(px.x,0)),heightAt(uv+vec2(0,px.y))-heightAt(uv-vec2(0,px.y)));
 vec3 n=normalize(vec3(-grad*uFinish.x,1)),l=normalize(vec3(uFinish.w,.7,1.4));
 float diffuse=.52+.48*max(dot(n,l),0.);
 float wet=clamp(surface.b,0.,1.);
 vec3 halfway=normalize(l+vec3(0,0,1));
 float spec=pow(max(dot(n,halfway),0.),mix(14.,72.,wet))*mix(.10,.85,wet)*smoothstep(.005,.08,h);
 float grain=fract(sin(dot(floor(uv*vec2(1024,640)),vec2(12.9898,78.233)))*43758.5453);
 vec3 wall=texture(sTD2DInputs[2],uv).rgb;
 vec3 paint=ink.rgb*mix(1.,diffuse,clamp(h*4.,0.,1.))+vec3(spec)*ink.a;
 vec3 neon=(ink.rgb/max(ink.a,.0001)+vec3(.42)*pow(surface.r,12.))*surface.r*uFinish.y;
 fragColor=TDOutputSwizzle(vec4(wall*(1.-ink.a)+paint+neon,1));
}
