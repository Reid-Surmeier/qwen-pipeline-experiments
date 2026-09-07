# THROWAWAY: Can the existing pixel maps become one continuous zoomable atlas?
extends Node2D

const WIDTH := 4480.0
const HEIGHT := 3144.0
var atlas: Dictionary
var camera := Camera2D.new()
var world_root := Node2D.new()
var detail_root := Node2D.new()
var sheet := Sprite2D.new()
var status := Label.new()
var picker := OptionButton.new()
var sheet_button := Button.new()
var hud := HBoxContainer.new()
var detail_alpha := 0.0
var dragging := false
var touches: Dictionary = {}
var selected := "europe"
var mode := "atlas"
var last_position := Vector2.ZERO
var last_zoom := 1.0
var state_timer := 0.0
var buttons: Dictionary = {}
var notice := Label.new()
var annotations: Array = []
var layout_position := Vector2.INF
var layout_zoom := 0.0
var visible_annotations := 0
var visible_cities := 0
var visible_labels := 0
var shown_cities: Array = []
var overview_badges := Node2D.new()

func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	atlas = JSON.parse_string(FileAccess.get_file_as_string("res://atlas.json"))
	add_child(world_root)
	add_child(overview_badges)
	add_child(detail_root)
	add_child(sheet)
	sheet.visible = false
	for copy in [-2, -1, 0, 1, 2]:
		var shift := Vector2(copy * WIDTH, 0)
		_sprite(world_root, "terrain", shift, Vector2.ONE)
		_sprite(overview_badges, "world-badges", shift, Vector2.ONE)
	for region in atlas.regions:
		var labels_texture: Texture2D = load("res://assets/" + region.id + "-labels.png")
		var symbols_texture: Texture2D = load("res://assets/" + region.id + "-annotations.png")
		for group in region.annotations:
			var sprite := Sprite2D.new()
			var texture := AtlasTexture.new()
			texture.atlas = labels_texture if group.kind == "label" else symbols_texture
			texture.region = Rect2(group.rect[0], group.rect[1], group.rect[2], group.rect[3])
			sprite.texture = texture
			detail_root.add_child(sprite)
			annotations.append({"sprite": sprite, "at": Vector2(group.at[0], group.at[1]), "kind": group.kind, "region": region.id, "city_id": str(region.id) + str(group.get("city_id", -1)), "rank": group.get("rank", 0), "offset": Vector2(group.get("offset", [0, 0])[0], group.get("offset", [0, 0])[1]), "size": Vector2(group.rect[2], group.rect[3]), "scale": 10.0 / group.rect[3] if group.kind == "city" else 1.0})
	add_child(camera)
	camera.position_smoothing_enabled = false
	_build_ui()
	get_viewport().size_changed.connect(_resize)
	_reset()
	_publish_state()

func _sprite(parent: Node, id: String, at: Vector2, size_scale: Vector2) -> void:
	var sprite := Sprite2D.new()
	sprite.texture = load("res://assets/" + id + ".png")
	sprite.centered = false
	sprite.position = at
	sprite.scale = size_scale
	parent.add_child(sprite)

func _build_ui() -> void:
	var canvas := CanvasLayer.new()
	add_child(canvas)
	var panel := PanelContainer.new()
	panel.name = "Toolbar"
	panel.position = Vector2(14, 14)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("ffdce9")
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 9
	style.content_margin_bottom = 9
	panel.add_theme_stylebox_override("panel", style)
	canvas.add_child(panel)
	hud.add_theme_constant_override("separation", 6)
	panel.add_child(hud)
	var title := Label.new()
	title.text = "PIXEL ATLAS"
	title.add_theme_color_override("font_color", Color("292735"))
	hud.add_child(title)
	_button("World", _reset)
	picker.fit_to_longest_item = false
	picker.add_item("Jump to region")
	for region in atlas.regions:
		picker.add_item(region.name)
	picker.item_selected.connect(func(index: int):
		if index > 0: _focus_region(atlas.regions[index - 1].id))
	hud.add_child(picker)
	sheet_button = _button("Full sheet", _toggle_sheet)
	_button("−", func(): _zoom_at(1.0 / 1.3, _viewport_size() / 2))
	_button("+", func(): _zoom_at(1.3, _viewport_size() / 2))
	status.position = Vector2(18, 75)
	status.add_theme_color_override("font_color", Color("292735"))
	status.add_theme_font_size_override("font_size", 16)
	status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.add_child(status)
	notice.text = "Drag to move · Scroll / pinch to zoom · Double-click to explore · Home to reset"
	notice.add_theme_color_override("font_color", Color("292735"))
	notice.add_theme_font_size_override("font_size", 14)
	notice.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.add_child(notice)
	_resize()

func _button(text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(44, 36)
	button.pressed.connect(action)
	button.focus_mode = Control.FOCUS_NONE
	hud.add_child(button)
	buttons[text] = button
	return button

func _viewport_size() -> Vector2:
	return get_viewport_rect().size

func _fit_zoom() -> float:
	var size := _viewport_size() - Vector2(24, 120)
	return minf(size.x / WIDTH, size.y / HEIGHT)

func _reset() -> void:
	mode = "atlas"
	world_root.visible = true
	overview_badges.visible = true
	detail_root.visible = true
	sheet.visible = false
	sheet_button.text = "Full sheet"
	_resize()
	camera.position = Vector2(WIDTH / 2, HEIGHT / 2 - 35 / _fit_zoom())
	camera.zoom = Vector2.ONE * _fit_zoom()
	picker.selected = 0
	_publish_state()

func _focus_region(id: String) -> void:
	if mode == "sheet": _toggle_sheet()
	selected = id
	var region := _region(id)
	camera.position = Vector2(region.focus[0], region.focus[1])
	var fit := minf((_viewport_size().x - 60) / region.size[0], (_viewport_size().y - 160) / region.size[1])
	camera.zoom = Vector2.ONE * clampf(fit * 1.4, 0.9, 1.6)
	_constrain()
	_publish_state()

func _region(id: String) -> Dictionary:
	for region in atlas.regions:
		if region.id == id: return region
	return atlas.regions[0]

func _toggle_sheet() -> void:
	if mode == "atlas":
		last_position = camera.position
		last_zoom = camera.zoom.x
		mode = "sheet"
		sheet.texture = load("res://assets/" + selected + ".png")
		sheet.centered = false
		sheet.visible = true
		world_root.visible = false
		overview_badges.visible = false
		detail_root.visible = false
		camera.position = sheet.texture.get_size() / 2
		camera.zoom = Vector2.ONE * minf((_viewport_size().x - 32) / sheet.texture.get_width(), (_viewport_size().y - 140) / sheet.texture.get_height())
		sheet_button.text = "Back to atlas"
	else:
		mode = "atlas"
		sheet.visible = false
		world_root.visible = true
		overview_badges.visible = true
		detail_root.visible = true
		camera.position = last_position
		camera.zoom = Vector2.ONE * last_zoom
		sheet_button.text = "Full sheet"
	_resize()
	_publish_state()

func _resize() -> void:
	notice.position = Vector2(18, _viewport_size().y - 28)
	if _viewport_size().x < 750:
		hud.get_child(0).visible = false
		picker.custom_minimum_size.x = 100
		sheet_button.text = "Sheet" if mode == "atlas" else "Atlas"
		picker.clip_text = true
		notice.text = "Drag / pinch to explore · + / − to zoom"
	else:
		hud.get_child(0).visible = true
		picker.custom_minimum_size.x = 155
		sheet_button.text = "Full sheet" if mode == "atlas" else "Back to atlas"
		notice.text = "Drag to move · Scroll / pinch to zoom · Double-click to explore · Home to reset"

func _zoom_at(factor: float, anchor: Vector2) -> void:
	var before := camera.position + (anchor - _viewport_size() / 2) / camera.zoom.x
	var next := clampf(camera.zoom.x * factor, _fit_zoom() * 0.5, 12.0)
	camera.zoom = Vector2.ONE * next
	camera.position = before - (anchor - _viewport_size() / 2) / next
	_constrain()
	_publish_state()

func _constrain() -> void:
	if mode == "atlas":
		camera.position.x = fposmod(camera.position.x, WIDTH)
		camera.position.y = clampf(camera.position.y, 0, HEIGHT)
	else:
		camera.position = camera.position.clamp(Vector2.ZERO, sheet.texture.get_size())

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouse and event.device == -1: return
	if event is InputEventMouseButton:
		if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP: _zoom_at(1.18, event.position)
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN: _zoom_at(1 / 1.18, event.position)
		elif event.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_MIDDLE]:
			dragging = event.pressed
			if event.double_click and event.pressed: _zoom_at(2.0, event.position)
	elif event is InputEventMouseMotion and dragging:
		camera.position -= event.relative / camera.zoom.x
		_constrain()
	elif event is InputEventScreenTouch:
		if event.pressed: touches[event.index] = event.position
		else: touches.erase(event.index)
	elif event is InputEventScreenDrag:
		if touches.size() == 2 and touches.has(event.index):
			var keys := touches.keys()
			var old_center: Vector2 = (touches[keys[0]] + touches[keys[1]]) / 2
			var old_distance: float = touches[keys[0]].distance_to(touches[keys[1]])
			touches[event.index] = event.position
			var center: Vector2 = (touches[keys[0]] + touches[keys[1]]) / 2
			var distance: float = touches[keys[0]].distance_to(touches[keys[1]])
			if old_distance > 2: _zoom_at(distance / old_distance, old_center)
			camera.position -= (center - old_center) / camera.zoom.x
		else:
			touches[event.index] = event.position
			camera.position -= event.relative / camera.zoom.x
		_constrain()
	elif event is InputEventMagnifyGesture: _zoom_at(event.factor, event.position)
	elif event is InputEventPanGesture:
		camera.position += event.delta * 20 / camera.zoom.x
		_constrain()
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_HOME, KEY_ESCAPE: _reset()
			KEY_PLUS, KEY_EQUAL, KEY_KP_ADD: _zoom_at(1.3, _viewport_size() / 2)
			KEY_MINUS, KEY_KP_SUBTRACT: _zoom_at(1 / 1.3, _viewport_size() / 2)
			KEY_LEFT: camera.position.x -= 100 / camera.zoom.x
			KEY_RIGHT: camera.position.x += 100 / camera.zoom.x
			KEY_UP: camera.position.y -= 100 / camera.zoom.x
			KEY_DOWN: camera.position.y += 100 / camera.zoom.x
			KEY_F: _toggle_sheet()
		_constrain()

func _layout_annotations() -> void:
	layout_position = camera.position
	layout_zoom = camera.zoom.x
	var occupied: Dictionary = {}
	var accepted_cities: Dictionary = {}
	var city_points: Array[Vector2] = []
	var order := annotations.duplicate()
	order.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var pa := (0 if a.kind == "city" else (2 if a.kind == "badge" else 4)) + (0 if a.region == selected else 1)
		var pb := (0 if b.kind == "city" else (2 if b.kind == "badge" else 4)) + (0 if b.region == selected else 1)
		if pa != pb: return pa < pb
		return a.rank < b.rank)
	visible_annotations = 0
	visible_cities = 0
	visible_labels = 0
	shown_cities.clear()
	for item in order:
		var sprite: Sprite2D = item.sprite
		sprite.visible = false
		if camera.zoom.x < 0.65: continue
		if item.kind == "label" and not accepted_cities.has(item.city_id): continue
		var point: Vector2 = item.at
		point.x = camera.position.x + fposmod(point.x - camera.position.x + WIDTH / 2, WIDTH) - WIDTH / 2
		var offset: Vector2 = item.offset if item.kind == "label" else Vector2.ZERO
		sprite.position = point + offset / camera.zoom.x
		sprite.scale = Vector2.ONE * item.scale / camera.zoom.x
		var screen: Vector2 = (point - camera.position) * camera.zoom.x + _viewport_size() / 2 + offset
		var extent: Vector2 = item.size * item.scale
		var rect := Rect2(screen - extent / 2, extent).grow(3)
		if not rect.intersects(Rect2(Vector2.ZERO, _viewport_size())): continue
		if item.kind == "city":
			# Spatial thinning is continuous: more room reveals more original cities.
			var spaced := true
			for previous in city_points:
				if screen.distance_to(previous) < 55: spaced = false; break
			if not spaced: continue
			city_points.append(screen)
			accepted_cities[item.city_id] = true
			visible_cities += 1
			shown_cities.append({"id": item.city_id, "at": [point.x, point.y], "screen": [screen.x, screen.y]})
		else:
			var cells: Array[Vector2i] = []
			for x in range(floori(rect.position.x / 64), floori(rect.end.x / 64) + 1):
				for y in range(floori(rect.position.y / 64), floori(rect.end.y / 64) + 1):
					cells.append(Vector2i(x, y))
			var collides := false
			for cell in cells:
				for previous in occupied.get(cell, []):
					if rect.intersects(previous): collides = true
			if collides: continue
			for cell in cells:
				if not occupied.has(cell): occupied[cell] = []
				occupied[cell].append(rect)
			if item.kind == "label": visible_labels += 1
		sprite.visible = true
		visible_annotations += 1

func _process(delta: float) -> void:
	detail_alpha = 1.0 if camera.zoom.x >= 0.65 else 0.0
	overview_badges.modulate.a = 1.0 - smoothstep(0.5, 0.65, camera.zoom.x)
	if mode == "atlas":
		var distance := INF
		for region in atlas.regions:
			var point := Vector2(region.focus[0], region.focus[1])
			point.x = camera.position.x + fposmod(point.x - camera.position.x + WIDTH / 2, WIDTH) - WIDTH / 2
			var d := camera.position.distance_squared_to(point)
			if d < distance:
				distance = d
				selected = region.id
	if camera.position != layout_position or camera.zoom.x != layout_zoom:
		_layout_annotations()
	status.text = "%s · %s · %.1f×" % [("Antarctica" if camera.position.y > 2300 and mode == "atlas" else _region(selected).name) if camera.zoom.x > 0.4 else "World", "Full sheet" if mode == "sheet" else ("Regional detail" if detail_alpha > 0.8 else "Overview"), camera.zoom.x / _fit_zoom()]
	state_timer += delta
	if state_timer > 0.2:
		state_timer = 0
		_publish_state()

func _publish_state() -> void:
	if not is_inside_tree(): return
	var controls: Dictionary = {}
	for name in buttons:
		var rect: Rect2 = buttons[name].get_global_rect()
		controls[name] = [rect.position.x, rect.position.y, rect.size.x, rect.size.y]
	var pick := picker.get_global_rect()
	controls["regions"] = [pick.position.x, pick.position.y, pick.size.x, pick.size.y]
	var state := {"mode": mode, "region": selected, "zoom": camera.zoom.x, "zoom_ratio": camera.zoom.x / _fit_zoom(), "position": [camera.position.x, camera.position.y], "detail_alpha": detail_alpha, "visible_annotations": visible_annotations, "visible_cities": visible_cities, "visible_labels": visible_labels, "shown_cities": shown_cities, "zoom_min": _fit_zoom() * 0.5, "zoom_max": 12.0, "world_size": [WIDTH, HEIGHT], "regions": atlas.regions, "controls": controls, "viewport": [_viewport_size().x, _viewport_size().y], "popup": {"visible": picker.get_popup().visible, "position": [picker.get_popup().position.x, picker.get_popup().position.y], "size": [picker.get_popup().size.x, picker.get_popup().size.y]}, "touches": touches.size(), "fps": Engine.get_frames_per_second()}
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.atlasState=" + JSON.stringify(state), true)
