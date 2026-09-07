extends Control

const INSET := Vector2(12, 52)
const FRAME_EXTRA := Vector2(24, 64)
var frame := Panel.new()
var title := TextureRect.new()
var title_text := TextureRect.new()
var minimize := TextureButton.new()
var lock_button := TextureButton.new()
var container := SubViewportContainer.new()
var viewport := SubViewport.new()
var locked := false
var collapsed := false
var expanded_size := Vector2.ZERO
var action := ""
var edges := Vector2i.ZERO
var start_pointer := Vector2.ZERO
var start_rect := Rect2()
var state_timer := 0.0

func _ready() -> void:
	RenderingServer.set_default_clear_color(Color.WHITE)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color("e0f3f5")
	style.border_color = Color("98b6bc")
	style.set_border_width_all(2)
	style.set_corner_radius_all(20)
	frame.add_theme_stylebox_override("panel", style)
	add_child(frame)
	var gradient := Gradient.new()
	gradient.colors = PackedColorArray([Color("e4f5fb"), Color("bfd8f0"), Color("d9ebf3")])
	gradient.offsets = PackedFloat32Array([0, 0.7, 1])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill_from = Vector2.ZERO
	texture.fill_to = Vector2(0, 1)
	title.texture = texture
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(title)
	title_text.texture = _title_crop(Rect2(40, 6, 490, 28))
	title_text.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	title_text.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	title_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(title_text)
	minimize.texture_normal = _title_crop(Rect2(12, 10, 24, 24))
	minimize.ignore_texture_size = true
	minimize.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
	minimize.tooltip_text = "Collapse / expand map"
	minimize.pressed.connect(_collapse)
	frame.add_child(minimize)
	lock_button.texture_normal = _title_crop(Rect2(560, 10, 24, 24))
	lock_button.ignore_texture_size = true
	lock_button.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
	lock_button.tooltip_text = "Lock / unlock window position and size"
	lock_button.pressed.connect(func():
		locked = not locked
		lock_button.modulate = Color("7696c6") if locked else Color.WHITE)
	frame.add_child(lock_button)
	container.stretch = true
	container.clip_contents = true
	frame.add_child(container)
	viewport.gui_embed_subwindows = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(viewport)
	get_viewport().size_changed.connect(_fit_window)
	_fit_window()
	viewport.add_child(load("res://atlas.tscn").instantiate())

func _title_crop(rect: Rect2) -> AtlasTexture:
	var texture := AtlasTexture.new()
	texture.atlas = load("res://assets/window-title.png")
	texture.region = rect
	return texture

func _fit_window() -> void:
	frame.position = Vector2(16, 16)
	frame.size = get_viewport_rect().size - Vector2(32, 32)
	collapsed = false
	container.visible = true
	_layout()

func _layout() -> void:
	title.position = Vector2(12, 12)
	title.size = Vector2(frame.size.x - 24, 40)
	minimize.position = Vector2(18, 20)
	minimize.size = Vector2(24, 24)
	lock_button.position = Vector2(frame.size.x - 42, 20)
	lock_button.size = Vector2(24, 24)
	title_text.position = Vector2(48, 18)
	title_text.size = Vector2(minf(490, frame.size.x - 96), 28)
	container.position = INSET
	if not collapsed: container.size = (frame.size - FRAME_EXTRA).max(Vector2(2, 2))
	queue_redraw()
	_publish()

func _collapse() -> void:
	collapsed = not collapsed
	if collapsed:
		expanded_size = frame.size
		frame.size.y = 64
	else:
		frame.size = expanded_size
	container.visible = not collapsed
	_layout()

func _input(event: InputEvent) -> void:
	if event is InputEventMouse and event.device == -1: return
	var pointer := Vector2.ZERO
	var pressed := false
	var released := false
	var motion := false
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		pointer = event.position
		pressed = event.pressed
		released = not event.pressed
	elif event is InputEventMouseMotion:
		pointer = event.position
		motion = true
	elif event is InputEventScreenTouch:
		pointer = event.position
		pressed = event.pressed
		released = not event.pressed
	elif event is InputEventScreenDrag:
		pointer = event.position
		motion = true
	else: return
	if pressed and not locked:
		var rect := frame.get_global_rect()
		if not rect.has_point(pointer): return
		var local := pointer - rect.position
		edges = Vector2i(-1 if local.x < 10 else (1 if local.x > rect.size.x - 10 else 0), -1 if local.y < 10 else (1 if local.y > rect.size.y - 10 else 0))
		if edges != Vector2i.ZERO and not collapsed: action = "resize"
		elif local.y >= 12 and local.y < 52 and local.x > 48 and local.x < rect.size.x - 48: action = "drag"
		else: return
		start_pointer = pointer
		start_rect = rect
	elif released:
		if action.is_empty(): return
		action = ""
	elif motion and not action.is_empty():
		var delta := pointer - start_pointer
		var available := get_viewport_rect().size
		if action == "drag":
			frame.position = (start_rect.position + delta).clamp(Vector2.ZERO, (available - frame.size).max(Vector2.ZERO))
		else:
			var low := start_rect.position
			var high := start_rect.end
			var minimum := Vector2(336, 280).min(available)
			for axis in [0, 1]:
				if edges[axis] < 0: low[axis] = clampf(low[axis] + delta[axis], 0, high[axis] - minimum[axis])
				if edges[axis] > 0: high[axis] = clampf(high[axis] + delta[axis], low[axis] + minimum[axis], available[axis])
			frame.position = low
			frame.size = high - low
		_layout()
	else: return
	get_viewport().set_input_as_handled()

func _draw() -> void:
	if collapsed: return
	for offset in [3, 7]:
		var corner := frame.position + frame.size - Vector2(4, 4)
		draw_line(corner - Vector2(offset, 0), corner - Vector2(0, offset), Color("91b1b8"), 1)

func _process(delta: float) -> void:
	state_timer += delta
	if state_timer > 0.2:
		state_timer = 0
		_publish()

func _publish() -> void:
	if not OS.has_feature("web"): return
	var rect := container.get_global_rect()
	JavaScriptBridge.eval("window.atlasWindow=" + JSON.stringify({"position": [frame.position.x, frame.position.y], "size": [frame.size.x, frame.size.y], "map_rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y], "locked": locked, "collapsed": collapsed, "action": action}), true)
