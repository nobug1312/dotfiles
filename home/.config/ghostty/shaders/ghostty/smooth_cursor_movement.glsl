// smooth-cursor.glsl – Gliding Mode
// Simulates smooth cursor movement by interpolating between
// the previous and current cursor positions.

// ── Tunables ──────────────────────────────────────────────
const float DURATION  = 0.19;   // animation duration in seconds
const float EDGE_SOFT = 1.5;    // pixel softness on cursor edges
const float HIDE_MATCH = 0.12;  // color-match threshold for destination cursor masking
// ─────────────────────────────────────────────────────────

// Cubic ease-out: immediate movement, smooth deceleration into destination
float ease(float t) {
    return 1.0 - pow(1.0 - t, 3.0);
}

// Normalize coordinates to a -1..1 space
vec2 norm(vec2 value, float isPosition) {
    return (value * 2.0 - (iResolution.xy * isPosition)) / iResolution.y;
}

// Get center of a cursor rect (xy = bottom-left corner, zw = size)
vec2 getCursorCenter(vec4 cursor) {
    return vec2(cursor.x + cursor.z / 2.0, cursor.y - cursor.w / 2.0);
}

// Signed distance to an axis-aligned rectangle
float sdfRect(vec2 p, vec2 center, vec2 halfSize) {
    vec2 d = abs(p - center) - halfSize;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = texture(iChannel0, fragCoord.xy / iResolution.xy);

    vec2 vu = norm(fragCoord, 1.0);
    vec4 curr = vec4(norm(iCurrentCursor.xy, 1.0), norm(iCurrentCursor.zw, 0.0));
    vec4 prev = vec4(norm(iPreviousCursor.xy, 1.0), norm(iPreviousCursor.zw, 0.0));

    float elapsed = iTime - iTimeCursorChange;
    float t = clamp(elapsed / DURATION, 0.0, 1.0);
    float easedT = ease(t);

    vec2 currCenter = getCursorCenter(curr);
    vec2 prevCenter = getCursorCenter(prev);
    vec2 halfSize = curr.zw * 0.5;

    float dist = distance(currCenter, prevCenter);
    bool animating = t < 1.0 && dist > 0.0001;

    if (animating) {
        vec2 lerpCenter = mix(prevCenter, currCenter, easedT);

        float sdfReal = sdfRect(vu, currCenter, halfSize);
        float sdfAnim = sdfRect(vu, lerpCenter, halfSize);

        // Hide the real cursor at the destination while the animated cursor moves.
        // Sample a fallback background color from the previous cursor cell and
        // apply it only to pixels that closely match the cursor color.
        // Only mask parts of the real destination cursor that are not already
        // covered by the animated cursor. This prevents early destination flashes.
        if (sdfReal <= 0.0 && sdfAnim > 0.0) {
            vec2 prevBgPixel = iPreviousCursor.xy + iPreviousCursor.zw * vec2(0.5, -0.5);
            prevBgPixel = clamp(prevBgPixel, vec2(0.0), iResolution.xy);
            vec4 bgColor = texture(iChannel0, prevBgPixel / iResolution.xy);

            // Tight threshold to target destination cursor-colored pixels only.
            float cursorMatch = 1.0 - smoothstep(0.0, HIDE_MATCH, distance(fragColor.rgb, iCurrentCursorColor.rgb));
            fragColor = mix(fragColor, bgColor, cursorMatch);
        }

        // Draw the animated cursor at the interpolated position
        float aaSize = norm(vec2(EDGE_SOFT, 0.0), 0.0).x;
        float alpha = 1.0 - smoothstep(-aaSize, 0.0, sdfAnim);
        if (alpha > 0.001) {
            fragColor = mix(fragColor, iCurrentCursorColor, iCurrentCursorColor.a * alpha);
        }
    }
}
