out vec4 fragColor;
uniform vec4 uArtwork;

void main()
{
    vec2 uv = vUV.st;
    float outputAspect = uTDOutputInfo.res.z / uTDOutputInfo.res.w;
    if (uArtwork.x > 0.5) {
        float artAspect = uTD2DInfos[2].res.z / uTD2DInfos[2].res.w;
        vec2 scale = max(vec2(1.0), vec2(outputAspect / artAspect, artAspect / outputAspect));
        vec2 artUV = (uv - 0.5) * scale + 0.5;
        vec3 color = vec3(18, 17, 44) / 255.0;
        if (all(greaterThanEqual(artUV, vec2(0))) && all(lessThanEqual(artUV, vec2(1)))) {
            vec3 artwork = texture(sTD2DInputs[2], artUV).rgb;
            float mask = texture(sTD2DInputs[3], artUV).r * smoothstep(0.55, 0.90, artwork.r);
            float coverage = texture(sTD2DInputs[4], artUV).a;
            vec3 paint = texture(sTD2DInputs[0], artUV).rgb;
            color = mix(artwork, clamp(artwork * (1.0 - coverage) + paint, 0.0, 1.0), mask);
        }
        fragColor = TDOutputSwizzle(vec4(color, 1.0));
        return;
    }
    vec3 scene = texture(sTD2DInputs[0], uv).rgb;
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
