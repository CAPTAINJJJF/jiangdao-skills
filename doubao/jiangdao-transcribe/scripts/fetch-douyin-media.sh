#!/bin/bash
set -euo pipefail

VIDEO_URL="${1:-}"
OUTPUT_FILE="${2:-}"
SEC_UID="${3:-}"

if [ -z "$VIDEO_URL" ] || [ -z "$OUTPUT_FILE" ]; then
  echo "用法: fetch-douyin-media.sh <抖音视频 URL> <输出 MP4> [作者 sec_uid]" >&2
  exit 1
fi

for command_name in opencli jq curl ffprobe; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "缺少命令: $command_name" >&2
    exit 1
  fi
done

AWEME_ID="$(printf '%s' "$VIDEO_URL" | sed -E 's#.*(/video/|modal_id=)([0-9]+).*#\2#')"
if ! printf '%s' "$AWEME_ID" | grep -Eq '^[0-9]+$'; then
  echo "无法从链接解析作品 ID: $VIDEO_URL" >&2
  exit 1
fi

SESSION="jiangdao-douyin-${AWEME_ID}-$$"
TAB_ID=""
cleanup() {
  opencli browser "$SESSION" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [ -z "$SEC_UID" ]; then
  OPEN_RESULT="$(opencli browser "$SESSION" open "$VIDEO_URL" --window background)"
  TAB_ID="$(printf '%s' "$OPEN_RESULT" | jq -r '.page // empty')"
  if [ -z "$TAB_ID" ]; then
    echo "抖音详情页未返回浏览器标签 ID" >&2
    exit 1
  fi

  AUTHOR_LINKS="$(opencli browser "$SESSION" eval 'Array.from(document.querySelectorAll("a[href*=\"/user/\"]")).map(a=>a.href).filter(h=>!/\/user\/self(?:[/?]|$)/.test(h))' --tab "$TAB_ID")"
  SEC_UID="$(printf '%s' "$AUTHOR_LINKS" | jq -r '.[0] // empty' | sed -E 's#^https?://www\.douyin\.com/user/([^?]+).*$#\1#')"
  if [ -z "$SEC_UID" ]; then
    echo "无法从详情页定位作者 sec_uid；请先确认页面可见和登录状态" >&2
    exit 2
  fi
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/jiangdao-douyin-${AWEME_ID}.XXXXXX")"
POSTS_JSON="$WORK_DIR/posts.json"
opencli douyin user-videos "$SEC_UID" --limit 20 --with_comments false -f json > "$POSTS_JSON"

PLAY_URL="$(jq -r --arg id "$AWEME_ID" '.[] | select((.aweme_id | tostring) == $id) | .play_url' "$POSTS_JSON" | head -n 1)"
if [ -z "$PLAY_URL" ] || [ "$PLAY_URL" = "null" ]; then
  echo "作者最近 20 条公开作品中未找到 ${AWEME_ID}；需进入后备采集路线" >&2
  exit 3
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"
curl --fail --location --retry 3 --retry-all-errors \
  --user-agent 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/138 Safari/537.36' \
  --referer 'https://www.douyin.com/' \
  --output "$OUTPUT_FILE" "$PLAY_URL"

if [ ! -s "$OUTPUT_FILE" ]; then
  echo "媒体下载结果为空: $OUTPUT_FILE" >&2
  exit 4
fi

PROBE_JSON="$(ffprobe -v error -show_entries format=duration,size,format_name -of json "$OUTPUT_FILE")"
FORMAT_NAME="$(printf '%s' "$PROBE_JSON" | jq -r '.format.format_name // empty')"
DURATION="$(printf '%s' "$PROBE_JSON" | jq -r '.format.duration // empty')"
SIZE="$(printf '%s' "$PROBE_JSON" | jq -r '.format.size // empty')"
if [ -z "$DURATION" ] || [ "$DURATION" = "N/A" ]; then
  echo "ffprobe 无法确认媒体时长: $OUTPUT_FILE" >&2
  exit 5
fi

jq -n \
  --arg source_url "$VIDEO_URL" \
  --arg aweme_id "$AWEME_ID" \
  --arg sec_uid "$SEC_UID" \
  --arg output_file "$OUTPUT_FILE" \
  --arg format_name "$FORMAT_NAME" \
  --arg duration "$DURATION" \
  --arg size "$SIZE" \
  '{source_url:$source_url,aweme_id:$aweme_id,sec_uid:$sec_uid,output_file:$output_file,format_name:$format_name,duration_seconds:($duration|tonumber),size_bytes:($size|tonumber),verified:true}'

rm -rf "$WORK_DIR"
