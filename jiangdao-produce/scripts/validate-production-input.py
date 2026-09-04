#!/usr/bin/env python3
"""Validate a per-content production input package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MODES = {"high_fidelity", "mixed_creation", "soul_creation"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="validate production input gate")
    parser.add_argument("path", help="生产资料审计 JSON")
    return parser.parse_args()


def is_true(value: Any) -> bool:
    return value is True


def usable_external(source: dict[str, Any]) -> bool:
    return (
        source.get("kind") == "external_source"
        and is_true(source.get("full_text"))
        and is_true(source.get("traceable"))
        and is_true(source.get("relevant"))
    )


def valid_user_original(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and is_true(value.get("present"))
        and is_true(value.get("concrete_start"))
        and is_true(value.get("confirmed_judgment"))
        and isinstance(value.get("source_ref"), str)
        and bool(value.get("source_ref", "").strip())
    )


def valid_user_auxiliary(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and is_true(value.get("present"))
        and (is_true(value.get("concrete_start")) or is_true(value.get("confirmed_judgment")))
        and isinstance(value.get("source_ref"), str)
        and bool(value.get("source_ref", "").strip())
    )


def main() -> int:
    args = parse_args()
    try:
        data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PRODUCTION_INPUT_FAILED\nINPUT_INVALID: {exc}")
        return 1

    failures: list[str] = []
    if data.get("schema_version") != "production-input-gate-v1":
        failures.append("SCHEMA_VERSION_INVALID")

    mode = data.get("production_mode")
    if mode not in MODES:
        failures.append("PRODUCTION_MODE_INVALID")

    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list):
        failures.append("SOURCES_INVALID")
        raw_sources = []
    sources = [item for item in raw_sources if isinstance(item, dict)]
    usable = [item for item in sources if usable_external(item)]
    user_original = data.get("user_original_content")
    user_original_ok = valid_user_original(user_original)
    user_auxiliary_ok = valid_user_auxiliary(user_original)

    ids = [item.get("id") for item in sources]
    if any(not isinstance(value, str) or not value.strip() for value in ids):
        failures.append("SOURCE_ID_MISSING")
    if len(ids) != len(set(ids)):
        failures.append("SOURCE_ID_DUPLICATED")

    if mode == "high_fidelity":
        if not is_true(data.get("high_fidelity_instruction_explicit")):
            failures.append("HIGH_FIDELITY_INSTRUCTION_MISSING")
        target_id = data.get("target_source_id")
        target = next((item for item in usable if item.get("id") == target_id), None)
        if target is None:
            failures.append("HIGH_FIDELITY_SOURCE_INCOMPLETE")

    elif mode == "mixed_creation":
        if not is_true(data.get("topic_confirmed")):
            failures.append("TOPIC_NOT_CONFIRMED")
        if not is_true(data.get("production_decision_confirmed")):
            failures.append("PRODUCTION_DECISION_NOT_CONFIRMED")
        if not usable:
            failures.append("MIXED_MAIN_SOURCE_MISSING")

        source_functions = {
            str(item.get("function", "")).strip()
            for item in usable
            if str(item.get("function", "")).strip()
        }
        distinct_inputs = len(usable) + (1 if user_auxiliary_ok else 0)
        distinct_functions = len(source_functions) + (1 if user_auxiliary_ok else 0)
        if distinct_inputs < 2 or distinct_functions < 2:
            failures.append("MIXED_INPUT_INSUFFICIENT")

    elif mode == "soul_creation":
        if not is_true(data.get("topic_confirmed")):
            failures.append("TOPIC_NOT_CONFIRMED")
        if not is_true(data.get("production_decision_confirmed")):
            failures.append("PRODUCTION_DECISION_NOT_CONFIRMED")
        if not user_original_ok:
            failures.append("SOUL_CORE_MISSING")
        expected_status = "available" if usable else "unavailable"
        if data.get("market_calibration_status") != expected_status:
            failures.append("MARKET_CALIBRATION_STATUS_INVALID")

    if failures:
        print("PRODUCTION_INPUT_FAILED")
        print("\n".join(dict.fromkeys(failures)))
        return 1

    print(
        f"PRODUCTION_INPUT_OK mode={mode} usable_sources={len(usable)} "
        "batch_target_required=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
