#!/usr/bin/env python3
"""Build a capcut-cli compile spec from a normalized ChatCut timeline manifest."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def require_number(obj: dict[str, Any], key: str, *, positive: bool = False) -> float:
    value = obj.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{key} must be a number")
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"{key} must be {'> 0' if positive else 'finite'}")
    return value


def round_seconds(value: float) -> float:
    return round(value, 9)


def build_spec(manifest: dict[str, Any]) -> dict[str, Any]:
    name = manifest.get("name")
    if not isinstance(name, str) or not name.strip() or "/" in name or "\\" in name:
        raise ValueError("name must be a plain non-empty draft folder name")

    fps = require_number(manifest, "fps", positive=True)
    width = int(require_number(manifest, "width", positive=True))
    height = int(require_number(manifest, "height", positive=True))
    output_speed = float(manifest.get("output_speed", 1.1))
    if not math.isfinite(output_speed) or output_speed <= 0:
        raise ValueError("output_speed must be > 0")

    raw_video_tracks = manifest.get("video_tracks")
    if raw_video_tracks is None:
        raw_video_tracks = [
            {
                "name": "主视频",
                "working_media_path": manifest.get("working_media_path"),
                "working_width": manifest.get("working_width", width),
                "working_height": manifest.get("working_height", height),
                "allow_timeline_gaps": manifest.get("allow_timeline_gaps", False),
                "clips": manifest.get("clips"),
            }
        ]
    if not isinstance(raw_video_tracks, list) or not raw_video_tracks:
        raise ValueError("video_tracks must be a non-empty list when provided")

    tracks: list[dict[str, Any]] = []
    for track_index, raw_track in enumerate(raw_video_tracks, 1):
        if not isinstance(raw_track, dict):
            raise ValueError(f"video_tracks[{track_index - 1}] must be an object")
        track_name = raw_track.get("name", f"视频轨{track_index}")
        if not isinstance(track_name, str) or not track_name.strip():
            raise ValueError(f"video_tracks[{track_index - 1}].name must be non-empty")
        media_path = raw_track.get("working_media_path")
        if not isinstance(media_path, str) or not Path(media_path).is_absolute():
            raise ValueError(
                f"video_tracks[{track_index - 1}].working_media_path must be an absolute path"
            )
        if not Path(media_path).exists():
            raise ValueError(f"working_media_path does not exist: {media_path}")
        clips = raw_track.get("clips")
        if not isinstance(clips, list) or not clips:
            raise ValueError(f"video_tracks[{track_index - 1}].clips must be a non-empty list")

        working_width = int(raw_track.get("working_width", width))
        working_height = int(raw_track.get("working_height", height))
        allow_gaps = bool(raw_track.get("allow_timeline_gaps", False))
        video_items: list[dict[str, Any]] = []
        previous_end: float | None = None

        for clip_index, raw in enumerate(clips, 1):
            if not isinstance(raw, dict):
                raise ValueError(
                    f"video_tracks[{track_index - 1}].clips[{clip_index - 1}] must be an object"
                )
            start_frame = require_number(raw, "timeline_start_frame")
            duration_frames = require_number(raw, "duration_frames", positive=True)
            source_start_frame = require_number(raw, "source_start_frame")
            playback_rate = float(raw.get("playback_rate", 1))
            if start_frame < 0 or source_start_frame < 0:
                raise ValueError(
                    f"video_tracks[{track_index - 1}].clips[{clip_index - 1}] "
                    "frame values must be >= 0"
                )
            if not math.isfinite(playback_rate) or playback_rate <= 0:
                raise ValueError(
                    f"video_tracks[{track_index - 1}].clips[{clip_index - 1}].playback_rate "
                    "must be > 0"
                )

            if previous_end is not None:
                delta = start_frame - previous_end
                if delta < -0.001:
                    raise ValueError(
                        f"video_tracks[{track_index - 1}].clips[{clip_index - 1}] "
                        f"overlaps the previous clip by {-delta} frames"
                    )
                if not allow_gaps and delta > 0.001:
                    raise ValueError(
                        f"video_tracks[{track_index - 1}].clips[{clip_index - 1}] "
                        f"starts {delta} frames after the previous clip"
                    )
            previous_end = start_frame + duration_frames

            video_items.append(
                {
                    "ref": f"v{track_index:02d}_{clip_index:04d}",
                    "path": media_path,
                    "start": round_seconds(start_frame / fps / output_speed),
                    "duration": round_seconds(duration_frames / fps / output_speed),
                    "sourceStart": round_seconds(source_start_frame / fps),
                    "speed": round(playback_rate * output_speed, 9),
                    "width": working_width,
                    "height": working_height,
                }
            )
        tracks.append({"type": "video", "name": track_name, "items": video_items})

    captions = manifest.get("captions")
    if captions is not None:
        if not isinstance(captions, list) or not captions:
            raise ValueError("captions must be a non-empty list when provided")
        style = manifest.get("caption_style", {})
        if not isinstance(style, dict):
            raise ValueError("caption_style must be an object")
        text_items: list[dict[str, Any]] = []
        for index, raw in enumerate(captions, 1):
            if not isinstance(raw, dict):
                raise ValueError(f"captions[{index - 1}] must be an object")
            start_frame = require_number(raw, "start_frame")
            end_frame = require_number(raw, "end_frame")
            text = raw.get("text")
            if start_frame < 0 or end_frame <= start_frame:
                raise ValueError(f"captions[{index - 1}] must have end_frame > start_frame >= 0")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"captions[{index - 1}].text must be non-empty")
            item: dict[str, Any] = {
                "ref": f"c{index:04d}",
                "text": text,
                "start": round_seconds(start_frame / fps / output_speed),
                "duration": round_seconds((end_frame - start_frame) / fps / output_speed),
            }
            for key in ("fontSize", "color", "x", "y"):
                if key in style:
                    item[key] = style[key]
            text_items.append(item)
        tracks.append({"type": "text", "name": "字幕", "items": text_items})

    return {
        "name": name,
        "width": width,
        "height": height,
        "fps": fps,
        "ratio": manifest.get("ratio", "original"),
        "tracks": tracks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    spec = build_spec(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), "tracks": len(spec["tracks"]), "items": sum(len(track["items"]) for track in spec["tracks"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
