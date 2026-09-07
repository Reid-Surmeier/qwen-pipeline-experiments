shader_type canvas_item;
render_mode unshaded;
uniform float map_zoom = 1.0;
void fragment() {
    vec2 distance_px = texture(TEXTURE, UV).rg * 255.0 - 128.0;
    float stroke = 32.0 / map_zoom;
    vec3 pink = vec3(255.0, 220.0, 233.0) / 255.0;
    vec3 cyan = vec3(131.0, 229.0, 247.0) / 255.0;
    vec3 color = distance_px.x > 0.0 ? pink : cyan;
    if (distance_px.x <= 0.0 && distance_px.x >= -stroke) color = vec3(1.0);
    if (distance_px.x > 0.0 && distance_px.y >= -stroke) color = vec3(1.0);
    if (distance_px.y > 0.0) color = cyan;
    COLOR = vec4(color, COLOR.a);
}
