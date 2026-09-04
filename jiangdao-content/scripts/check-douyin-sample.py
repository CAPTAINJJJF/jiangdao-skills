#!/usr/bin/env python3
"""Validate a Douyin sample across acquisition, content, and market evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

EVIDENCE_MODES = {"speech_primary", "hybrid", "visual_primary"}
REVIEW_STATES = {"passed", "pending", "failed", "not_applicable"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(base_dir: Path, raw: Any) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def existing_file(path: Path | None) -> bool:
    return bool(path and path.is_file() and path.stat().st_size > 0)


def probe_media(path: Path | None) -> dict[str, Any]:
    if not existing_file(path):
        return {"status": "failed", "failures": ["media_missing_or_empty"]}
    assert path is not None
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,format_name,size:stream=codec_name,width,height",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
        duration = float(payload.get("format", {}).get("duration") or 0)
        if duration <= 0:
            return {"status": "failed", "failures": ["media_duration_invalid"]}
        return {
            "status": "passed",
            "failures": [],
            "size_bytes": path.stat().st_size,
            "duration_seconds": round(duration, 3),
            "format": payload.get("format", {}).get("format_name", ""),
            "streams": payload.get("streams", []),
        }
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError):
        return {"status": "failed", "failures": ["ffprobe_failed"]}


def first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def evaluate_metadata(path: Path | None, minimum_likes: int) -> dict[str, Any]:
    if not existing_file(path):
        return {"status": "failed", "failures": ["metadata_missing_or_empty"]}
    assert path is not None
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "failed", "failures": ["metadata_json_invalid"]}

    author = payload.get("author") or {}
    statistics = payload.get("statistics") or {}
    author_name = author.get("nickname") if isinstance(author, dict) else author
    values = {
        "aweme_id": first_value(payload.get("aweme_id"), payload.get("id")),
        "description": first_value(payload.get("desc"), payload.get("item_title"), payload.get("title")),
        "author": first_value(author_name, payload.get("author_name")),
        "published_at": first_value(payload.get("create_time"), payload.get("published_at")),
        "likes": first_value(statistics.get("digg_count"), payload.get("digg_count"), payload.get("likes")),
    }
    content_keys = ("aweme_id", "description", "author", "published_at")
    failures = [f"metadata_{key}_missing" for key in content_keys if values[key] in (None, "")]
    likes = to_int(values["likes"])
    return {
        "status": "failed" if failures else "passed",
        "failures": failures,
        "aweme_id": str(values["aweme_id"] or ""),
        "likes": likes,
        "minimum_likes": minimum_likes,
        "likes_gate": "passed" if likes is not None and likes >= minimum_likes else "failed",
    }


def normalized_comment(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def evaluate_comments(path: Path | None, minimum_comments: int) -> dict[str, Any]:
    if not existing_file(path):
        return {
            "status": "failed",
            "failures": ["comments_missing_or_empty"],
            "raw_count": 0,
            "effective_count": 0,
        }
    assert path is not None
    try:
        payload = read_json(path)
        comments = payload.get("comments") if isinstance(payload, dict) else payload
        if not isinstance(comments, list):
            comments = []
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "status": "failed",
            "failures": ["comments_json_invalid"],
            "raw_count": 0,
            "effective_count": 0,
        }

    effective_count = 0
    for item in comments:
        if isinstance(item, dict):
            text = str(first_value(item.get("text"), item.get("content"), "") or "").strip()
        else:
            text = str(item).strip()
        if len(normalized_comment(text)) >= 2:
            effective_count += 1
    failures = [] if effective_count >= minimum_comments else ["effective_comments_insufficient"]
    return {
        "status": "failed" if failures else "passed",
        "failures": failures,
        "raw_count": len(comments),
        "effective_count": effective_count,
        "minimum_comments": minimum_comments,
    }


def run_transcript_checker(
    checker: Path,
    media_path: Path | None,
    asr_path: Path | None,
    transcript_path: Path | None,
) -> dict[str, Any]:
    if not existing_file(checker):
        return {"qualified": False, "failures": ["transcript_checker_missing"]}
    if not all(existing_file(path) for path in (media_path, asr_path, transcript_path)):
        return {"qualified": False, "failures": ["transcript_inputs_missing"]}
    assert media_path is not None and asr_path is not None and transcript_path is not None
    completed = subprocess.run(
        ["node", str(checker), str(media_path), str(asr_path), str(transcript_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"qualified": False, "failures": ["transcript_checker_output_invalid"]}


def review_status(
    review: Any,
    label: str,
    allowed_not_applicable: bool = False,
) -> tuple[str, str]:
    if not isinstance(review, dict):
        return "pending", f"{label}_review_missing"
    status = str(review.get("status") or "pending")
    if status not in REVIEW_STATES or (status == "not_applicable" and not allowed_not_applicable):
        return "pending", f"{label}_review_status_invalid"
    return status, ""


def evaluate_manifest(manifest_path: Path) -> dict[str, Any]:
    base_dir = manifest_path.resolve().parent
    manifest = read_json(manifest_path)
    minimum_likes = int(manifest.get("minimum_likes", 1000))
    minimum_comments = int(manifest.get("minimum_effective_comments", 3))
    evidence_mode = str(manifest.get("evidence_mode") or "unknown")

    media_path = resolve_path(base_dir, manifest.get("media_file"))
    metadata_path = resolve_path(base_dir, manifest.get("metadata_file"))
    comments_path = resolve_path(base_dir, manifest.get("comments_file"))
    asr_path = resolve_path(base_dir, manifest.get("asr_file"))
    transcript_path = resolve_path(base_dir, manifest.get("transcript_file"))
    checker = Path(__file__).with_name("check-douyin-transcript.js")

    media = probe_media(media_path)
    metadata = evaluate_metadata(metadata_path, minimum_likes)
    comments = evaluate_comments(comments_path, minimum_comments)
    transcript_required = evidence_mode in {"speech_primary", "hybrid"}
    transcript = run_transcript_checker(checker, media_path, asr_path, transcript_path)

    semantic_status, semantic_error = review_status(
        manifest.get("semantic_review"),
        "semantic",
        allowed_not_applicable=evidence_mode == "visual_primary",
    )
    if evidence_mode == "visual_primary" and semantic_status == "not_applicable":
        semantic_passed = True
    else:
        semantic_passed = semantic_status == "passed"

    visual_required = evidence_mode in {"hybrid", "visual_primary"}
    visual_status, visual_error = review_status(
        manifest.get("visual_review"),
        "visual",
        allowed_not_applicable=not visual_required,
    )
    visual_failures: list[str] = []
    if visual_error:
        visual_failures.append(visual_error)
    if visual_required and visual_status == "passed":
        review = manifest.get("visual_review") or {}
        evidence_files = review.get("evidence_files") or []
        if not isinstance(evidence_files, list) or not evidence_files:
            visual_failures.append("visual_evidence_missing")
        else:
            for raw in evidence_files:
                if not existing_file(resolve_path(base_dir, raw)):
                    visual_failures.append("visual_evidence_missing")
                    break
    visual_passed = (not visual_required and visual_status in {"passed", "not_applicable"}) or (
        visual_required and visual_status == "passed" and not visual_failures
    )

    comments_review_status, comments_review_error = review_status(
        manifest.get("comments_review"),
        "comments",
    )
    comments_review_passed = comments_review_status == "passed"

    acquisition_ready = media.get("status") == "passed" and metadata.get("status") == "passed"
    transcript_passed = bool(transcript.get("qualified")) if transcript_required else True
    evidence_mode_valid = evidence_mode in EVIDENCE_MODES
    content_ready = (
        acquisition_ready
        and evidence_mode_valid
        and transcript_passed
        and semantic_passed
        and visual_passed
    )
    market_ready = (
        content_ready
        and comments.get("status") == "passed"
        and comments_review_passed
        and metadata.get("likes_gate") == "passed"
    )

    if market_ready:
        job_status = "completed"
        sample_state = "market_ready"
    elif content_ready:
        job_status = "partial"
        sample_state = "content_ready"
    elif acquisition_ready:
        job_status = "partial"
        sample_state = "candidate"
    elif metadata.get("status") == "passed":
        job_status = "partial"
        sample_state = "index_only"
    else:
        job_status = "failed"
        sample_state = "failed"

    blockers: list[str] = []
    for section_name, section in (("media", media), ("metadata", metadata), ("comments", comments)):
        blockers.extend(f"{section_name}:{item}" for item in section.get("failures", []))
    if evidence_mode not in EVIDENCE_MODES:
        blockers.append("review:evidence_mode_unknown")
    if transcript_required:
        blockers.extend(f"transcript:{item}" for item in transcript.get("failures", []))
        if semantic_error:
            blockers.append(f"review:{semantic_error}")
        if semantic_status == "pending":
            blockers.append("review:semantic_review_pending")
        elif semantic_status == "failed":
            blockers.append("review:semantic_review_failed")
    if visual_error:
        blockers.append(f"review:{visual_error}")
    blockers.extend(f"review:{item}" for item in visual_failures)
    if visual_required and visual_status == "pending":
        blockers.append("review:visual_review_pending")
    elif visual_required and visual_status == "failed":
        blockers.append("review:visual_review_failed")
    if comments_review_error:
        blockers.append(f"review:{comments_review_error}")
    if comments_review_status == "pending":
        blockers.append("review:comments_review_pending")
    elif comments_review_status == "failed":
        blockers.append("review:comments_review_failed")
    if metadata.get("likes_gate") != "passed":
        blockers.append("metadata:likes_below_threshold_or_missing")

    return {
        "sample_id": str(first_value(manifest.get("sample_id"), metadata.get("aweme_id"), "")),
        "job_status": job_status,
        "sample_state": sample_state,
        "qualified": market_ready,
        "acquisition_ready": acquisition_ready,
        "content_ready": content_ready,
        "market_ready": market_ready,
        "evidence_mode": evidence_mode,
        "artifact_status": {
            "media": media.get("status"),
            "metadata": metadata.get("status"),
            "comments": comments.get("status"),
            "comments_review": comments_review_status,
            "asr": "not_required" if not transcript_required else (
                "passed" if transcript.get("qualified") else "failed"
            ),
            "transcript": "not_required" if not transcript_required else (
                "passed" if transcript.get("qualified") and semantic_passed else "failed"
            ),
            "semantic_review": semantic_status,
            "visual_review": visual_status,
        },
        "blockers": sorted(set(blockers)),
        "details": {
            "media": media,
            "metadata": metadata,
            "comments": comments,
            "transcript": transcript,
            "reviews": {
                "semantic": semantic_status,
                "visual": visual_status,
                "comments": comments_review_status,
            },
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="验收单条抖音采集样本")
    parser.add_argument("manifest", type=Path, help="样本验收清单 JSON")
    parser.add_argument("--output", type=Path, help="可选的验收报告输出路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = evaluate_manifest(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"job_status": "failed", "error": str(error)}, ensure_ascii=False, indent=2))
        return 2
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    sys.stdout.write(output)
    return 0 if report["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
