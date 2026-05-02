#!/usr/bin/env bash
# Run from the project root: bash demo/run_demo.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"

PY=python3
RAW="demo/raw_output.txt"
MESH="demo/mesh_output.txt"
PACKET="demo/CONTEXT_PACKET.md"

echo "============================================="
echo "ContextMesh demo - token savings on a real bug"
echo "============================================="
echo

$PY -m contextmesh.cli.main init >/dev/null
$PY -m contextmesh.cli.main index demo >/dev/null

echo "1. Raw pytest output (what your agent normally sees):"
PYTHONPATH="$ROOT_DIR/demo/src" $PY -m pytest demo/tests/auth/test_reset.py >"$RAW" 2>&1 || true
RAW_LINES=$(wc -l <"$RAW" | tr -d ' ')
RAW_BYTES=$(wc -c <"$RAW" | tr -d ' ')
echo "   $RAW_LINES lines, $RAW_BYTES bytes."
echo

echo "2. ContextMesh-distilled output:"
PYTHONPATH="$ROOT_DIR/demo/src" $PY -m contextmesh.cli.main run pytest demo/tests/auth/test_reset.py >"$MESH" 2>&1 || true
MESH_LINES=$(wc -l <"$MESH" | tr -d ' ')
MESH_BYTES=$(wc -c <"$MESH" | tr -d ' ')
echo "   $MESH_LINES lines, $MESH_BYTES bytes."
echo

echo "3. Bundled context packet for the agent:"
$PY -m contextmesh.cli.main export-context \
    --task "Fix reset token expiry bug" \
    --task-id reset-bug \
    --path demo \
    --format markdown \
    --out "$PACKET" >/dev/null
PACKET_BYTES=$(wc -c <"$PACKET" | tr -d ' ')
echo "   wrote $PACKET ($PACKET_BYTES bytes)."
echo

$PY - <<'PY'
import tiktoken, pathlib
enc = tiktoken.get_encoding("cl100k_base")
raw = pathlib.Path("demo/raw_output.txt").read_text(errors="ignore")
mesh = pathlib.Path("demo/mesh_output.txt").read_text(errors="ignore")
packet = pathlib.Path("demo/CONTEXT_PACKET.md").read_text(errors="ignore")
raw_t, mesh_t, packet_t = (len(enc.encode(s)) for s in (raw, mesh, packet))
saved = (raw_t - mesh_t) / raw_t * 100 if raw_t else 0
print(f"raw pytest tokens          : {raw_t:>6}")
print(f"contextmesh run tokens     : {mesh_t:>6}  ({saved:5.1f}% smaller)")
print(f"context packet bundle      : {packet_t:>6}  (handed to the agent once)")
PY

echo
echo "Done. See demo/CONTEXT_PACKET.md for the bundle your agent should consume."
