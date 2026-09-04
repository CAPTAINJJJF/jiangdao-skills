#!/usr/bin/env python3
"""Validate the short single-source state card used by Jiangdao editing tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROUTES = {"not_selected", "local_a_roll", "chatcut_edit", "chatcut_jianying", "full_package"}
HANDOFF_MODES = {"not_selected", "direct_multitrack", "clean_base_overlay_srt"}
STAGES = {
    "workflow_planning",
    "workflow_confirmation",
    "workflow_confirmed",
    "intake",
    "content_review",
    "aroll_edit",
    "packaging",
    "handoff_preflight",
    "handoff_build",
    "jianying_verify",
    "delivered",
}
EXECUTION_STAGES = STAGES - {"workflow_planning", "workflow_confirmation"}
EVIDENCE_KEYS = (
    "assets_imported",
    "tracks_created",
    "captions_on_timeline",
    "draft_saved",
    "playback_checked",
)


def require_object(parent: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def require_text(parent: dict[str, Any], key: str, errors: list[str], prefix: str = "") -> str:
    value = parent.get(key)
    label = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return ""
    return value.strip()


def validate_state(state: dict[str, Any], *, check_paths: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    require_text(state, "schema_version", errors)
    require_text(state, "task_id", errors)
    require_text(state, "updated_at", errors)
    project_root = require_text(state, "project_root", errors)
    if project_root and not Path(project_root).is_absolute():
        errors.append("project_root must be an absolute path")
    elif check_paths and project_root and not Path(project_root).exists():
        errors.append(f"project_root does not exist: {project_root}")

    stage = require_text(state, "stage", errors)
    route = require_text(state, "route_lock", errors)
    if stage and stage not in STAGES:
        errors.append(f"stage {stage!r} is not supported")
    if route and route not in ROUTES:
        errors.append(f"route_lock {route!r} is not supported")

    workflow = require_object(state, "workflow", errors)
    workflow_type = require_text(workflow, "type", errors, "workflow")
    workflow_version = require_text(workflow, "version", errors, "workflow")
    require_text(workflow, "summary", errors, "workflow")
    confirmed_at = workflow.get("confirmed_at")
    if stage in EXECUTION_STAGES:
        if not isinstance(confirmed_at, str) or not confirmed_at.strip():
            errors.append("workflow.confirmed_at is required before execution")
        if route == "not_selected":
            errors.append("route_lock must be selected before execution")
    elif confirmed_at not in (None, "") and not isinstance(confirmed_at, str):
        errors.append("workflow.confirmed_at must be a string or null")

    scope = require_object(state, "scope", errors)
    delivery = scope.get("delivery")
    if not isinstance(delivery, list) or not delivery or not all(isinstance(item, str) and item for item in delivery):
        errors.append("scope.delivery must be a non-empty string list")
    acceptance = scope.get("acceptance")
    if not isinstance(acceptance, str) or not acceptance.strip():
        errors.append("scope.acceptance must be a non-empty string")

    chatcut = require_object(state, "chatcut", errors)
    if stage in {"packaging", "handoff_preflight", "handoff_build", "jianying_verify", "delivered"}:
        require_text(chatcut, "project_id", errors, "chatcut")
        formal_id = require_text(chatcut, "formal_timeline_id", errors, "chatcut")
        require_text(chatcut, "formal_timeline_name", errors, "chatcut")
    else:
        formal_id = str(chatcut.get("formal_timeline_id", "")).strip()

    mcp_id = str(chatcut.get("mcp_timeline_id", "")).strip()
    desktop_id = str(chatcut.get("desktop_visible_timeline_id", "")).strip()
    if stage in {"handoff_build", "jianying_verify", "delivered"}:
        if not mcp_id or not desktop_id:
            errors.append("handoff build requires both MCP and desktop-visible timeline IDs")
        elif len({formal_id, mcp_id, desktop_id}) != 1:
            errors.append("formal, MCP and desktop-visible timeline IDs must match")

    capabilities = require_object(state, "capabilities", errors)
    if stage in {"handoff_build", "jianying_verify", "delivered"}:
        for key in ("jianying_install", "chatcut_plan", "transparent_motion_export"):
            value = capabilities.get(key)
            if value in (None, "", "unknown", "unchecked"):
                errors.append(f"capabilities.{key} must be checked before full build")

    handoff = require_object(state, "handoff", errors)
    mode = require_text(handoff, "mode", errors, "handoff")
    if mode and mode not in HANDOFF_MODES:
        errors.append(f"handoff.mode {mode!r} is not supported")
    if stage in {"handoff_build", "jianying_verify", "delivered"} and mode == "not_selected":
        errors.append("handoff.mode must be locked before full build")

    output_paths = handoff.get("output_paths", {})
    if not isinstance(output_paths, dict):
        errors.append("handoff.output_paths must be an object")
        output_paths = {}
    required_outputs: tuple[str, ...] = ()
    if mode == "direct_multitrack":
        required_outputs = ("draft",)
    elif mode == "clean_base_overlay_srt":
        required_outputs = ("clean_project", "base_video", "motion_overlay", "subtitles_srt", "draft")
    if stage in {"handoff_build", "jianying_verify", "delivered"}:
        for key in required_outputs:
            value = output_paths.get(key)
            if not isinstance(value, str) or not Path(value).is_absolute():
                errors.append(f"handoff.output_paths.{key} must be an absolute path")
            elif check_paths and stage in {"jianying_verify", "delivered"} and not Path(value).exists():
                errors.append(f"handoff output does not exist: {value}")

    evidence = require_object(state, "evidence", errors)
    for key in EVIDENCE_KEYS:
        if not isinstance(evidence.get(key), bool):
            errors.append(f"evidence.{key} must be boolean")
    if evidence.get("tracks_created") and not evidence.get("assets_imported"):
        errors.append("tracks_created requires assets_imported")
    if evidence.get("captions_on_timeline") and not evidence.get("tracks_created"):
        errors.append("captions_on_timeline requires tracks_created")
    if evidence.get("draft_saved") and not evidence.get("tracks_created"):
        errors.append("draft_saved requires tracks_created")
    if evidence.get("playback_checked") and not evidence.get("draft_saved"):
        errors.append("playback_checked requires draft_saved")

    if stage == "delivered":
        for key in ("assets_imported", "tracks_created", "draft_saved", "playback_checked"):
            if evidence.get(key) is not True:
                errors.append(f"delivered requires evidence.{key}=true")
        if "subtitles_srt" in (delivery or []) and evidence.get("captions_on_timeline") is not True:
            errors.append("delivered subtitles require captions_on_timeline=true")

    return {
        "ok": not errors,
        "task_id": state.get("task_id"),
        "stage": stage,
        "route_lock": route,
        "workflow_type": workflow_type,
        "workflow_version": workflow_version,
        "workflow_confirmed": isinstance(confirmed_at, str) and bool(confirmed_at.strip()),
        "handoff_mode": mode,
        "timeline_ids_match": bool(formal_id and formal_id == mcp_id == desktop_id),
        "evidence": {key: evidence.get(key) for key in EVIDENCE_KEYS},
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--check-paths", action="store_true")
    args = parser.parse_args()

    raw = json.loads(args.state.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("state card root must be an object")
    result = validate_state(raw, check_paths=args.check_paths)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
