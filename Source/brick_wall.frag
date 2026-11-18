out vec4 fragColor;

float hash(vec2 point)
{
    vec3 p = fract(vec3(point.xyx) * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
}

float noise(vec2 point)
{
    vec2 cell = floor(point);
    vec2 f = fract(point);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(cell), hash(cell + vec2(1, 0)), f.x),
               mix(hash(cell + vec2(0, 1)), hash(cell + vec2(1, 1)), f.x), f.y);
}

void main()
{
    vec2 uv = vUV.st;
    vec2 pixel = uv * vec2(1024, 640);
    vec2 brickSize = vec2(128, 55);
    float course = floor(pixel.y / brickSize.y);
    vec2 staggered = pixel + vec2(0.5 * brickSize.x * mod(course, 2.0), 0);
    vec2 id = floor(staggered / brickSize);
    vec2 local = mod(staggered, brickSize);

    vec2 distanceToEdge = min(local, brickSize - local);
    float chippedEdge = (noise(pixel * 0.23) - 0.5) * 2.5;
    float edge = min(distanceToEdge.x, distanceToEdge.y) + chippedEdge;
    float brickFace = smoothstep(1.6, 3.3, edge);
    float bevel = brickFace * (1.0 - smoothstep(3.0, 7.5, edge));
    float edgeLight = distanceToEdge.x < distanceToEdge.y
        ? (local.x < brickSize.x * 0.5 ? 0.07 : -0.07)
        : (local.y < brickSize.y * 0.5 ? -0.08 : 0.10);

    float grain = hash(floor(pixel));
    float mottling = 0.62 * noise(pixel * vec2(0.034, 0.070))
                   + 0.38 * noise(pixel * vec2(0.11, 0.19));
    float pits = smoothstep(0.64, 0.91, noise(pixel * 0.64));
    vec3 clay = mix(vec3(0.19, 0.097, 0.073), vec3(0.35, 0.204, 0.155), hash(id));
    clay += vec3(0.12, 0.092, 0.079) * (mottling - 0.5);
    clay += vec3(0.027 * (grain - 0.5) - 0.028 * pits + bevel * edgeLight);

    vec3 base = texture(sTD2DInputs[0], uv).rgb;
    vec3 mortar = 0.35 * base + vec3(0.090, 0.082, 0.075)
                + vec3(0.026 * (grain - 0.5) + 0.017 * (noise(pixel * 0.19) - 0.5));
    mortar *= mix(0.83, 1.0, smoothstep(1.0, 2.7, abs(edge - 2.2)));

    vec2 fromLight = (uv - vec2(0.46, 0.68)) * vec2(0.9, 0.8);
    float illumination = 1.10 - 0.46 * dot(fromLight, fromLight);
    fragColor = TDOutputSwizzle(vec4(mix(mortar, clay, brickFace) * illumination, 1.0));
}
