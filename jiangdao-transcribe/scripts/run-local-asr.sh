#!/bin/bash
set -euo pipefail

INPUT="${1:-}"
OUTPUT_DIR="${2:-}"
TERMS_FILE="${3:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_ROOT="${JIANGDAO_ASR_CACHE_DIR:-$HOME/.cache/jiangdao-asr}"
VENV_DIR="$CACHE_ROOT/venv"
PYTHON_BIN="${JIANGDAO_ASR_PYTHON:-$VENV_DIR/bin/python}"
LOCAL_MODEL="$CACHE_ROOT/models/whisper-large-v3-turbo-q4"
if [ -n "${JIANGDAO_ASR_MODEL_PATH:-}" ]; then
  MODEL_REF="$JIANGDAO_ASR_MODEL_PATH"
elif [ -s "$LOCAL_MODEL/weights.npz" ] && [ -s "$LOCAL_MODEL/config.json" ]; then
  MODEL_REF="$LOCAL_MODEL"
else
  MODEL_REF="mlx-community/whisper-large-v3-turbo-q4"
fi

if [ -z "$INPUT" ] || [ -z "$OUTPUT_DIR" ]; then
  echo "用法: run-local-asr.sh <音视频文件> <独立输出目录> [专名表.txt]" >&2
  exit 1
fi
if [ ! -f "$INPUT" ]; then
  echo "找不到输入文件: $INPUT" >&2
  exit 1
fi
if [ -n "$TERMS_FILE" ] && [ ! -f "$TERMS_FILE" ]; then
  echo "找不到专名表: $TERMS_FILE" >&2
  exit 1
fi
if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "当前本地引擎需要 Apple Silicon Mac。" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "缺少 ffmpeg/ffprobe，请先安装后重试。" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR" "$CACHE_ROOT"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
INPUT_DIR="$(cd "$(dirname "$INPUT")" && pwd)"
INPUT_ABS="$INPUT_DIR/$(basename "$INPUT")"

if [ ! -x "$PYTHON_BIN" ] || ! "$PYTHON_BIN" -c 'import mlx_whisper' >/dev/null 2>&1; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "缺少 uv，无法自动准备本地 MLX Whisper 运行环境。" >&2
    exit 1
  fi
  echo "首次运行：准备本地 MLX Whisper 环境..."
  uv venv --python 3.12 "$VENV_DIR"
  uv pip install --python "$VENV_DIR/bin/python" 'mlx-whisper==0.4.3'
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

echo "本地转写：$(basename "$INPUT_ABS")"
"$PYTHON_BIN" "$SCRIPT_DIR/local-transcribe.py" \
  "$INPUT_ABS" "$OUTPUT_DIR" "$MODEL_REF" "$TERMS_FILE"
