#!/bin/bash
#
# Adapted from chengfeng-videocut-skills under Apache-2.0.
# Modified 2026-08-13 by 江导项目: uses the cached local MLX Whisper wrapper.
#
# Generate raw transcript files from a finished/cut video.
#
# Usage:
#   generate-srt-from-video.sh <video.mp4> <subtitle_output_dir>
#
# Output:
#   <subtitle_output_dir>/1_转录/asr_result.json
#   <subtitle_output_dir>/subtitles_with_time.json
#   <subtitle_output_dir>/3_输出/video.raw.srt
#

set -euo pipefail

VIDEO_PATH="${1:-}"
OUTPUT_DIR="${2:-}"

if [ -z "$VIDEO_PATH" ] || [ -z "$OUTPUT_DIR" ]; then
  echo "用法: generate-srt-from-video.sh <video.mp4> <subtitle_output_dir>" >&2
  exit 1
fi

if [ ! -f "$VIDEO_PATH" ]; then
  echo "找不到视频文件: $VIDEO_PATH" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRANSCRIBE_SCRIPT="$SCRIPT_DIR/run-local-asr.sh"

mkdir -p "$OUTPUT_DIR/1_转录" "$OUTPUT_DIR/3_输出"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
VIDEO_DIR="$(cd "$(dirname "$VIDEO_PATH")" && pwd)"
VIDEO_PATH="$VIDEO_DIR/$(basename "$VIDEO_PATH")"

echo "🎤 转写当前成片（命中缓存时直接复用）..."
bash "$TRANSCRIBE_SCRIPT" "$VIDEO_PATH" "$OUTPUT_DIR/1_转录"

cd "$OUTPUT_DIR/1_转录"

node - <<'NODE'
const fs = require('fs');
const result = JSON.parse(fs.readFileSync('asr_result.json', 'utf8'));
const utterances = result.utterances || result.result?.utterances || [];

const subtitles = utterances.map((u, i) => ({
  id: i + 1,
  text: u.text || '',
  start: (u.start_time ?? u.start ?? 0) / 1000,
  end: (u.end_time ?? u.end ?? 0) / 1000
}));

fs.writeFileSync('../subtitles_with_time.json', JSON.stringify(subtitles, null, 2));

function toSRT(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.round((sec % 1) * 1000);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}

const srt = subtitles.map((item, i) => {
  const text = item.text.replace(/[。！？]+$/g, '');
  return `${i + 1}\n${toSRT(item.start)} --> ${toSRT(item.end)}\n${text}`;
}).join('\n\n');

fs.writeFileSync('../3_输出/video.raw.srt', srt.trim() + '\n');
console.log(`✅ 已生成 ${subtitles.length} 条转写初稿: ../3_输出/video.raw.srt`);
NODE

echo "✅ Raw SRT: $OUTPUT_DIR/3_输出/video.raw.srt"
echo "下一步：对照当前视频、确认稿和专名表校对，再写入 $OUTPUT_DIR/3_输出/video.srt"
