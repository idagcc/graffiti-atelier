out vec4 fragColor;

void main()
{
    vec2 uv = vUV.st;
    vec3 scene = texture(sTD2DInputs[0], uv).rgb;
    float outputAspect = uTDOutputInfo.res.z / uTDOutputInfo.res.w;
    float logoAspect = uTD2DInfos[1].res.z / uTD2DInfos[1].res.w;
    float width = min(0.45, 0.125 * logoAspect / outputAspect);
    vec2 size = vec2(width, width * outputAspect / logoAspect);
    vec2 origin = vec2((1.0 - size.x) * 0.5, 0.972 - size.y);
    vec2 logoUV = (uv - origin) / size;
    if (all(greaterThanEqual(logoUV, vec2(0.0))) && all(lessThanEqual(logoUV, vec2(1.0)))) {
        vec4 logo = texture(sTD2DInputs[1], logoUV);
        scene = scene * (1.0 - logo.a) + logo.rgb;
    }
    fragColor = TDOutputSwizzle(vec4(scene, 1.0));
}
