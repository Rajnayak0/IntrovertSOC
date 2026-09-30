#!/usr/bin/env sh
# Convenience wrapper to start a llamafile server for IntrovertSOC.
# The llamafile binary and GGUF model are NOT bundled (see NETWORK.md) - point
# this script at your own copies.
#
#   LLAMAFILE=/path/to/llamafile LLAMAFILE_MODEL_PATH=/path/to/model.gguf \
#     ./scripts/start_llamafile.sh

set -eu
BINARY="${LLAMAFILE:-}"
MODEL="${LLAMAFILE_MODEL_PATH:-}"
PORT="${LLAMAFILE_PORT:-8080}"

[ -n "$BINARY" ] || { echo "Missing llamafile binary: set LLAMAFILE" >&2; exit 1; }
[ -n "$MODEL" ]  || { echo "Missing GGUF model: set LLAMAFILE_MODEL_PATH" >&2; exit 1; }
[ -x "$BINARY" ] || [ -f "$BINARY" ] || { echo "Binary not found: $BINARY" >&2; exit 1; }
[ -f "$MODEL" ]  || { echo "Model not found: $MODEL" >&2; exit 1; }

echo "Starting local LLM at http://127.0.0.1:${PORT} (loopback only)"
exec "$BINARY" -m "$MODEL" --server --host 127.0.0.1 --port "$PORT"
