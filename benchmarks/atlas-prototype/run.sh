#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
GODOT_BIN="${GODOT_BIN:-/home/reidsurmeier/.cache/qwen-ui-pipeline/godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64}"
mkdir -p web
"$GODOT_BIN" --headless --path godot --editor --import --quit
"$GODOT_BIN" --headless --path godot --export-release Web "$PWD/web/index.html"
python3 /home/reidsurmeier/agentic-workflow/scripts/share.py "$PWD/web" --label pixel-atlas-prototype --reason 'Requested zoomable Godot atlas prototype' --keep 3d
