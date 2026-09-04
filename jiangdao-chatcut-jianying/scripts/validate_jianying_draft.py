#!/usr/bin/env python3
"""Validate a generated JianYing draft's editable timeline and media links."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def load_draft(path: Path) -> tuple[Path, dict[str, Any]]:
    file_path = path / "draft_content.json" if path.is_dir() else path
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("draft_content.json root must be an object")
    return file_path, data


def parse_int_list(value: str) -> list[int]:
    try:
        result = [int(item) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a comma-separated integer list") from exc
    if not result or any(item < 0 for item in result):
        raise argparse.ArgumentTypeError("track clip counts must be non-negative")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--expected-video-clips", type=int)
    parser.add_argument("--expected-video-tracks", type=int)
    parser.add_argument("--expected-video-track-clips", type=parse_int_list)
    parser.add_argument("--expected-text-tracks", type=int)
    parser.add_argument("--expected-text-segments", type=int)
    parser.add_argument("--expected-speed", type=float)
    parser.add_argument("--expected-media", type=Path, action="append")
    parser.add_argument("--expected-unused-video-materials", type=int)
    parser.add_argument("--expected-unused-text-materials", type=int)
    parser.add_argument("--expected-duration-us", type=int)
    parser.add_argument("--expected-first-text-start-us", type=int)
    parser.add_argument("--expected-last-text-end-us", type=int)
    parser.add_argument("--duration-tolerance-us", type=int, default=50_000)
    parser.add_argument("--gap-tolerance-us", type=int, default=1_000)
    parser.add_argument("--allow-video-gaps", action="store_true")
    parser.add_argument("--require-video-start-zero", action="store_true")
    parser.add_argument("--require-video-equal-end", action="store_true")
    args = parser.parse_args()

    file_path, draft = load_draft(args.draft)
    errors: list[str] = []
    warnings: list[str] = []
    tracks = draft.get("tracks", [])
    video_tracks = [track for track in tracks if track.get("type") == "video"]
    text_tracks = [track for track in tracks if track.get("type") == "text"]
    video_segments = [segment for track in video_tracks for segment in track.get("segments", [])]
    text_segments = [segment for track in text_tracks for segment in track.get("segments", [])]

    if args.expected_video_tracks is not None and len(video_tracks) != args.expected_video_tracks:
        errors.append(f"video track count {len(video_tracks)} != {args.expected_video_tracks}")
    if args.expected_text_tracks is not None and len(text_tracks) != args.expected_text_tracks:
        errors.append(f"text track count {len(text_tracks)} != {args.expected_text_tracks}")
    if args.expected_text_segments is not None and len(text_segments) != args.expected_text_segments:
        errors.append(f"text segment count {len(text_segments)} != {args.expected_text_segments}")

    if args.expected_video_clips is not None and len(video_segments) != args.expected_video_clips:
        errors.append(f"video clip count {len(video_segments)} != {args.expected_video_clips}")
    actual_track_clips = [len(track.get("segments", [])) for track in video_tracks]
    if args.expected_video_track_clips is not None and actual_track_clips != args.expected_video_track_clips:
        errors.append(f"video track clip counts {actual_track_clips} != {args.expected_video_track_clips}")

    speeds: list[float] = []
    video_track_summaries: list[dict[str, Any]] = []
    for track_index, track in enumerate(video_tracks):
        segments = sorted(
            track.get("segments", []),
            key=lambda segment: segment.get("target_timerange", {}).get("start", 0),
        )
        previous_end: int | None = None
        first_start: int | None = None
        for segment_index, segment in enumerate(segments):
            target = segment.get("target_timerange", {})
            start = target.get("start")
            duration = target.get("duration")
            label = f"video track {track_index} segment {segment_index}"
            if not isinstance(start, int) or not isinstance(duration, int) or duration <= 0:
                errors.append(f"{label} has invalid target_timerange")
                continue
            if first_start is None:
                first_start = start
                if args.require_video_start_zero and abs(start) > args.gap_tolerance_us:
                    errors.append(f"video track {track_index} starts at {start}us instead of 0")
            if previous_end is not None:
                delta = start - previous_end
                if delta < -args.gap_tolerance_us:
                    errors.append(f"{label} overlaps previous by {-delta}us")
                elif not args.allow_video_gaps and delta > args.gap_tolerance_us:
                    errors.append(f"{label} has a {delta}us gap")
            previous_end = start + duration
            speed = segment.get("speed", 1)
            if isinstance(speed, (int, float)) and not isinstance(speed, bool):
                speeds.append(float(speed))
            else:
                errors.append(f"{label} has invalid speed")
        video_track_summaries.append(
            {
                "name": track.get("name", ""),
                "clips": len(segments),
                "start_us": first_start,
                "end_us": previous_end,
            }
        )

    video_track_ends = [
        summary["end_us"] for summary in video_track_summaries if summary["end_us"] is not None
    ]
    if (
        args.require_video_equal_end
        and video_track_ends
        and max(video_track_ends) - min(video_track_ends) > args.duration_tolerance_us
    ):
        errors.append(
            f"video track ends {video_track_ends} differ by more than "
            f"{args.duration_tolerance_us}us"
        )

    if args.expected_speed is not None:
        for index, speed in enumerate(speeds):
            if not math.isclose(speed, args.expected_speed, rel_tol=0, abs_tol=1e-6):
                errors.append(f"video segment {index} speed {speed} != {args.expected_speed}")

    materials = draft.get("materials", {})
    videos = materials.get("videos", [])
    texts = materials.get("texts", [])
    media_paths = sorted({item.get("path") for item in videos if isinstance(item.get("path"), str)})
    missing = [path for path in media_paths if not Path(path).exists()]
    if missing:
        errors.extend(f"missing media: {path}" for path in missing)

    if args.expected_media is not None:
        expected = sorted({str(path) for path in args.expected_media})
        if media_paths != expected:
            errors.append(f"material paths {media_paths!r} != {expected!r}")

    video_material_ids = {item.get("id") for item in videos if isinstance(item.get("id"), str)}
    referenced_video_ids = {
        segment.get("material_id")
        for segment in video_segments
        if isinstance(segment.get("material_id"), str)
    }
    missing_video_refs = sorted(referenced_video_ids - video_material_ids)
    if missing_video_refs:
        errors.extend(f"video segment references missing material: {item}" for item in missing_video_refs)
    unused_video_materials = sorted(video_material_ids - referenced_video_ids)
    if (
        args.expected_unused_video_materials is not None
        and len(unused_video_materials) != args.expected_unused_video_materials
    ):
        errors.append(
            f"unused video material count {len(unused_video_materials)} != "
            f"{args.expected_unused_video_materials}"
        )

    text_material_ids = {item.get("id") for item in texts if isinstance(item.get("id"), str)}
    referenced_text_ids = {
        segment.get("material_id")
        for segment in text_segments
        if isinstance(segment.get("material_id"), str)
    }
    missing_text_refs = sorted(referenced_text_ids - text_material_ids)
    if missing_text_refs:
        errors.extend(f"text segment references missing material: {item}" for item in missing_text_refs)
    unused_text_materials = sorted(text_material_ids - referenced_text_ids)
    if (
        args.expected_unused_text_materials is not None
        and len(unused_text_materials) != args.expected_unused_text_materials
    ):
        errors.append(
            f"unused text material count {len(unused_text_materials)} != "
            f"{args.expected_unused_text_materials}"
        )

    text_ranges: list[tuple[int, int]] = []
    for index, segment in enumerate(text_segments):
        target = segment.get("target_timerange", {})
        start = target.get("start")
        duration = target.get("duration")
        if not isinstance(start, int) or start < 0 or not isinstance(duration, int) or duration <= 0:
            errors.append(f"text segment {index} has invalid target_timerange")
            continue
        text_ranges.append((start, duration))
    text_ranges.sort()
    first_text_start = text_ranges[0][0] if text_ranges else None
    last_text_end = max((start + duration for start, duration in text_ranges), default=None)
    if args.expected_first_text_start_us is not None and first_text_start != args.expected_first_text_start_us:
        errors.append(f"first text start {first_text_start} != {args.expected_first_text_start_us}")
    if args.expected_last_text_end_us is not None and last_text_end != args.expected_last_text_end_us:
        errors.append(f"last text end {last_text_end} != {args.expected_last_text_end_us}")

    max_end = max(
        (
            segment.get("target_timerange", {}).get("start", 0)
            + segment.get("target_timerange", {}).get("duration", 0)
            for track in tracks
            for segment in track.get("segments", [])
        ),
        default=0,
    )
    declared_duration = draft.get("duration")
    if args.expected_duration_us is not None:
        if not isinstance(declared_duration, int):
            errors.append("draft duration is missing or invalid")
        elif abs(declared_duration - args.expected_duration_us) > args.duration_tolerance_us:
            errors.append(
                f"draft duration {declared_duration} differs from expected "
                f"{args.expected_duration_us} by more than {args.duration_tolerance_us}us"
            )
        if abs(max_end - args.expected_duration_us) > args.duration_tolerance_us:
            errors.append(
                f"timeline end {max_end} differs from expected {args.expected_duration_us} "
                f"by more than {args.duration_tolerance_us}us"
            )
    result = {
        "ok": not errors,
        "draft": str(file_path),
        "video_tracks": len(video_tracks),
        "video_clips": len(video_segments),
        "video_track_summaries": video_track_summaries,
        "text_tracks": len(text_tracks),
        "text_segments": len(text_segments),
        "first_text_start_us": first_text_start,
        "last_text_end_us": last_text_end,
        "declared_duration_us": declared_duration,
        "duration_us": max_end,
        "speeds": sorted(set(speeds)),
        "material_entries": len(videos),
        "media_paths": media_paths,
        "missing_media": len(missing),
        "unused_video_materials": unused_video_materials,
        "unused_text_materials": unused_text_materials,
        "warnings": warnings,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
