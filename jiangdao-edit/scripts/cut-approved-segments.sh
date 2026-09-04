#!/bin/bash
# Adapted from chengfeng-videocut-skills under Apache-2.0.
# Modified 2026-08-12 by 江导项目: argument-safe planning, bounded parallelism,
# input validation, and project-local naming.

set -euo pipefail

INPUT="${1:-}"
DELETE_JSON="${2:-}"
OUTPUT="${3:-output_cut.mp4}"
PARALLEL="${JIANGDAO_RENDER_JOBS:-2}"

if [ -z "$INPUT" ] || [ -z "$DELETE_JSON" ]; then
  echo "用法: cut-approved-segments.sh <input> <delete_segments.json> [output.mp4]"
  exit 1
fi
if [ ! -f "$INPUT" ]; then echo "找不到输入文件: $INPUT"; exit 1; fi
if [ ! -f "$DELETE_JSON" ]; then echo "找不到删除列表: $DELETE_JSON"; exit 1; fi
if ! [[ "$PARALLEL" =~ ^[1-9][0-9]*$ ]]; then echo "JIANGDAO_RENDER_JOBS 必须是正整数"; exit 1; fi

DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "file:$INPUT")"
CODEC="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "file:$INPUT")"
PROFILE="$(ffprobe -v error -select_streams v:0 -show_entries stream=profile -of csv=p=0 "file:$INPUT")"
PIX_FMT="$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of csv=p=0 "file:$INPUT")"
BITRATE="$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of csv=p=0 "file:$INPUT")"
if ! [[ "$BITRATE" =~ ^[0-9]+$ ]] || [ "$BITRATE" -lt 100000 ]; then BITRATE=8000000; fi
BITRATE_K=$((BITRATE / 1000))
MAXRATE_K=$((BITRATE_K * 13 / 10))
BUFSIZE_K=$((BITRATE_K * 2))

TASK_TMP="$(mktemp -d "${TMPDIR:-/tmp}/jiangdao-cut.XXXXXX")"
cleanup() { rm -rf "$TASK_TMP"; }
trap cleanup EXIT

PLAN_COUNT="$(node - "$DELETE_JSON" "$DURATION" "$TASK_TMP" <<'NODE'
const fs = require('fs');
const path = require('path');
const [deleteFile, durationRaw, taskDir] = process.argv.slice(2);
const duration = Number(durationRaw);
const input = JSON.parse(fs.readFileSync(deleteFile, 'utf8'));
if (!Array.isArray(input) || !Number.isFinite(duration) || duration <= 0) process.exit(2);
const ranges = input.map((item, index) => {
  const start = Number(item.start), end = Number(item.end);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || start >= duration) {
    throw new Error(`无效删除区间 ${index + 1}`);
  }
  return { start, end: Math.min(end, duration) };
}).sort((a, b) => a.start - b.start);
const merged = [];
for (const item of ranges) {
  const last = merged[merged.length - 1];
  if (!last || item.start > last.end + 0.2) merged.push({ ...item });
  else last.end = Math.max(last.end, item.end);
}
const keep = [];
let cursor = 0;
for (const item of merged) {
  if (item.start > cursor + 0.001) keep.push({ start: cursor, end: item.start });
  cursor = Math.max(cursor, item.end);
}
if (cursor < duration - 0.001) keep.push({ start: cursor, end: duration });
if (!keep.length) throw new Error('删除范围覆盖整条视频');
const rows = keep.map((item, index) => {
  const name = `segment_${String(index).padStart(5, '0')}.mp4`;
  return [item.start.toFixed(6), item.end.toFixed(6), path.join(taskDir, name)].join('\t');
});
fs.writeFileSync(path.join(taskDir, 'segments.tsv'), rows.join('\n') + '\n');
fs.writeFileSync(path.join(taskDir, 'concat.txt'), keep.map((_, index) =>
  `file '${path.join(taskDir, `segment_${String(index).padStart(5, '0')}.mp4`).replaceAll("'", "'\\''")}'`
).join('\n') + '\n');
console.error(`删除区间: ${merged.length}，保留片段: ${keep.length}`);
console.log(keep.length);
NODE
)"

PROFILE_LC="$(printf '%s' "$PROFILE" | tr '[:upper:]' '[:lower:]')"
if [ "$CODEC" = "hevc" ] && ffmpeg -hide_banner -encoders 2>/dev/null | grep -q 'hevc_videotoolbox'; then
  VIDEO_ENCODER="hevc_videotoolbox"
  case "$PROFILE_LC" in
    *"main 10"*) VIDEO_PROFILE="main10"; OUTPUT_PIX_FMT="p010le" ;;
    *) VIDEO_PROFILE="main"; OUTPUT_PIX_FMT="yuv420p" ;;
  esac
elif [ "$CODEC" = "hevc" ]; then
  VIDEO_ENCODER="libx265"
  case "$PROFILE_LC" in
    *"main 10"*) VIDEO_PROFILE="main10"; OUTPUT_PIX_FMT="yuv420p10le" ;;
    *) VIDEO_PROFILE="main"; OUTPUT_PIX_FMT="yuv420p" ;;
  esac
else
  VIDEO_ENCODER="libx264"
  OUTPUT_PIX_FMT="${PIX_FMT:-yuv420p}"
  case "$PROFILE_LC" in baseline) VIDEO_PROFILE="baseline" ;; main) VIDEO_PROFILE="main" ;; *) VIDEO_PROFILE="high" ;; esac
fi

echo "✂️ 渲染 ${PLAN_COUNT} 个确认片段（并行 ${PARALLEL}）"
export INPUT VIDEO_ENCODER VIDEO_PROFILE BITRATE_K MAXRATE_K BUFSIZE_K OUTPUT_PIX_FMT
PIDS=()
RUNNING=0
while IFS=$'\t' read -r START END TARGET; do
  (
    ffmpeg -y -v error -ss "$START" -to "$END" -accurate_seek -i "file:$INPUT" \
      -c:v "$VIDEO_ENCODER" -profile:v "$VIDEO_PROFILE" \
      -b:v "${BITRATE_K}k" -maxrate "${MAXRATE_K}k" -bufsize "${BUFSIZE_K}k" \
      -pix_fmt "$OUTPUT_PIX_FMT" -c:a aac -b:a 128k -avoid_negative_ts make_zero "file:$TARGET"
  ) &
  PIDS+=("$!")
  RUNNING=$((RUNNING + 1))
  if [ "$RUNNING" -ge "$PARALLEL" ]; then
    wait "${PIDS[0]}"
    PIDS=("${PIDS[@]:1}")
    RUNNING=$((RUNNING - 1))
  fi
done < "$TASK_TMP/segments.tsv"
for PID in "${PIDS[@]}"; do wait "$PID"; done

ffmpeg -y -v error -f concat -safe 0 -i "$TASK_TMP/concat.txt" -c copy -movflags +faststart "file:$OUTPUT"
NEW_DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "file:$OUTPUT")"
echo "✅ 已保存: $OUTPUT"
echo "📹 ${DURATION}s → ${NEW_DURATION}s"
