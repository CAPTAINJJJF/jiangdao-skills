#!/usr/bin/env python3
"""Validate topic candidates against the formal problem pool and backend audit."""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_COUNT = 10
LEGACY_GROUP_HEADINGS = ("市场痛点型", "高感知收益型", "本我内容种子型")
REQUIRED_FIELDS = ("题源原话", "生成关系", "建议", "来源")
ALLOWED_ACTIONS = {
    "未加工", "元素迁移", "选题具体化", "收益显化", "损失显化", "损益显化"
}
ALLOWED_DEVELOPMENT_PATHS = {
    "现场处理", "前兆诊断", "信号归并", "关系反差", "损益落地", "用户校准路径"
}
ALLOWED_TOPIC_FORMS = {"open_question", "directional_hypothesis"}
ACTION_ELEMENT_TYPES = {
    "元素迁移": {"人群", "对象", "阶段", "场景", "行业"},
    "选题具体化": {"人群", "时间", "场景", "阶段", "限制条件", "时代背景"},
    "收益显化": {"收益"},
    "损失显化": {"损失"},
    "损益显化": {"收益", "损失"},
}
REQUIRED_VERDICTS = (
    "core_need_preserved", "added_elements_grounded", "substantial_processing",
    "target_audience_fit", "stakes_visible", "whole_topic", "resonance_sufficient",
    "expression_space_preserved", "deliverable", "task_fit", "identity_safe",
)
REQUIRED_REASONS = (
    "semantic_relation", "grounding", "stakes", "audience", "capacity", "novelty",
    "deliverability", "identity",
)
REQUIRED_QUALITY_FIELDS = (
    "target_stakes", "target_click_reason", "content_capacity", "resonance_scope",
    "wrong_audience_risk",
)
SUGGESTION_MARKERS = ("可以考虑", "建议从", "可以从", "可以尝试", "可以讨论", "可以回答")
THIRD_PARTY_MARKERS = ("第三方案例", "原作者", "案例拆解", "这位创作者", "这个案例")
IDENTITY_RESULT_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:万|千)?\s*粉|年入\s*\d|月入\s*\d|年赚\s*\d|"
    r"月赚\s*\d|GMV\s*\d|带来\s*\d+\s*个客户|成交\s*\d+\s*万|服务过\s*\d+)"
)
ANSWER_LEAK_PATTERNS = (
    re.compile(r"(?:本质|答案|关键|真正原因|根本原因)(?:其实)?(?:就在于|在于|是)"),
    re.compile(r"只要.+就(?:能|会|可以)"),
    re.compile(r"(?:一定|必然)会"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="frontstage candidate Markdown")
    parser.add_argument("--audit", type=Path, required=True, help="backend topic audit JSON")
    parser.add_argument("--problem-pool", type=Path, required=True, help="formal single-track database JSON")
    parser.add_argument("--mode", choices=("single_source", "track_pool"), required=True)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    return parser.parse_args()


def compact(value: str) -> str:
    return re.sub(r"[\s\u3000]+", "", value or "")


def semantic_text(value: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", value or "").lower()


def strip_outer_quotes(value: str) -> str:
    value = value.strip()
    for left, right in (("“", "”"), ('"', '"'), ("‘", "’"), ("'", "'")):
        if value.startswith(left) and value.endswith(right) and len(value) >= 2:
            return value[1:-1].strip()
    return value


def char_bigrams(value: str) -> set[str]:
    text = semantic_text(value)
    return {text[index:index + 2] for index in range(max(0, len(text) - 1))}


def semantic_overlap(anchor: str, target: str) -> float:
    anchor_text = semantic_text(anchor)
    target_text = semantic_text(target)
    if not anchor_text or not target_text:
        return 0.0
    char_score = len(set(anchor_text) & set(target_text)) / max(1, len(set(anchor_text)))
    anchor_pairs = char_bigrams(anchor_text)
    target_pairs = char_bigrams(target_text)
    pair_score = len(anchor_pairs & target_pairs) / max(1, len(anchor_pairs))
    return 0.45 * char_score + 0.55 * pair_score


def topic_blocks(text: str) -> list[tuple[int, str, str]]:
    matches = list(re.finditer(r"^##\s+(\d+)｜(.+?)\s*$", text, re.MULTILINE))
    blocks: list[tuple[int, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((int(match.group(1)), match.group(2).strip(), text[match.end():end]))
    return blocks


def field_value(block: str, field: str) -> str | None:
    match = re.search(
        rf"^{re.escape(field)}：\s*(.+?)(?=^(?:{'|'.join(map(re.escape, REQUIRED_FIELDS))})：|\Z)",
        block,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else None


def load_json(path: Path, label: str, failures: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        failures.append(f"{label}_MISSING: {path}")
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f"{label}_INVALID: {path}: {error}")
    return None


def resolve_recorded_path(raw: Any, relative_to: Path) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = relative_to.parent / candidate
    return candidate.resolve()


def source_record_ids(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for raw in item.get("sources") or []:
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        elif isinstance(raw, dict):
            record_id = raw.get("record_id")
            if isinstance(record_id, str) and record_id.strip():
                values.append(record_id.strip())
    for raw in item.get("representative_samples") or []:
        if isinstance(raw, dict):
            record_id = raw.get("record_id")
            if isinstance(record_id, str) and record_id.strip():
                values.append(record_id.strip())
    return list(dict.fromkeys(values))


def problem_records(data: Any, failures: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("track_problem_pool"), list):
        failures.append("PROBLEM_POOL_INVALID: expected track_problem_pool array")
        return {}
    records: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(data["track_problem_pool"]):
        if not isinstance(item, dict):
            failures.append(f"PROBLEM_RECORD_INVALID [{index}]")
            continue
        problem_id = item.get("problem_id") or item.get("source_problem_id")
        problem = item.get("problem") or item.get("track_problem")
        if not isinstance(problem_id, str) or not problem_id.strip():
            failures.append(f"PROBLEM_ID_MISSING [{index}]")
            continue
        if not isinstance(problem, str) or not problem.strip():
            failures.append(f"PROBLEM_TEXT_MISSING [{problem_id}]")
            continue
        if problem_id in records:
            failures.append(f"PROBLEM_ID_DUPLICATE: {problem_id}")
            continue
        records[problem_id] = {
            "id": problem_id,
            "problem": problem.strip(),
            "source_record_ids": source_record_ids(item),
        }
    return records


def markdown_links(value: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", value)


def local_link_exists(raw: str, document_path: Path) -> bool:
    target = raw.split("#", 1)[0].strip()
    if target.startswith(("http://", "https://")):
        return True
    target = re.sub(r":\d+$", "", target)
    path = Path(target).expanduser()
    if not path.is_absolute():
        path = document_path.parent / path
    return path.exists()


def action_mentioned(action: str, relation: str) -> bool:
    return action in relation or (action in {"收益显化", "损失显化"} and "损益显化" in relation)


def near_duplicate(first: str, second: str) -> bool:
    left = semantic_text(first)
    right = semantic_text(second)
    if left == right:
        return True
    sequence_score = SequenceMatcher(None, left, right).ratio()
    left_pairs = char_bigrams(left)
    right_pairs = char_bigrams(right)
    pair_score = len(left_pairs & right_pairs) / max(1, len(left_pairs | right_pairs))
    return sequence_score >= 0.88 or (sequence_score >= 0.82 and pair_score >= 0.70)


def validate_audit_candidate(
    audit_item: Any,
    audit_path: Path,
    number: int,
    title: str,
    block: str,
    problems: dict[str, dict[str, Any]],
    allowed_problem_ids: set[str],
    allowed_evidence_paths: set[Path],
    evidence_cache: dict[Path, str],
    failures: list[str],
) -> None:
    label = f"[{number}] {title}"
    if not isinstance(audit_item, dict):
        failures.append(f"AUDIT_RECORD_INVALID {label}")
        return
    if audit_item.get("number") != number:
        failures.append(f"AUDIT_NUMBER_MISMATCH {label}")
    if audit_item.get("topic") != title:
        failures.append(f"AUDIT_TOPIC_MISMATCH {label}")

    source_id = audit_item.get("source_problem_id")
    source_problem = audit_item.get("source_problem")
    if not isinstance(source_id, str) or source_id not in problems:
        failures.append(f"SOURCE_PROBLEM_NOT_IN_POOL {label}: {source_id}")
        pool_problem = ""
    else:
        pool_problem = problems[source_id]["problem"]
        if source_problem != pool_problem:
            failures.append(f"AUDIT_SOURCE_TEXT_MISMATCH {label}")
    if isinstance(source_id, str) and source_id not in allowed_problem_ids:
        failures.append(f"SOURCE_PROBLEM_OUTSIDE_MODE_SCOPE {label}: {source_id}")
    displayed_source = strip_outer_quotes(field_value(block, "题源原话") or "")
    if pool_problem and displayed_source != pool_problem:
        failures.append(f"DISPLAYED_SOURCE_NOT_IN_POOL {label}")

    core_need = audit_item.get("core_need")
    if not isinstance(core_need, str) or len(semantic_text(core_need)) < 4:
        failures.append(f"CORE_NEED_MISSING {label}")
    elif pool_problem:
        if semantic_overlap(core_need, pool_problem) < 0.20:
            failures.append(f"CORE_NEED_DRIFT_FROM_SOURCE {label}")
        if semantic_overlap(core_need, title) < 0.12:
            failures.append(f"CORE_NEED_DRIFT_FROM_TOPIC {label}")

    actions = audit_item.get("processing_actions")
    if not isinstance(actions, list) or not actions or any(action not in ALLOWED_ACTIONS for action in actions):
        failures.append(f"PROCESSING_ACTION_INVALID {label}")
        actions = []
    if "未加工" in actions and len(actions) > 1:
        failures.append(f"PROCESSING_ACTION_CONFLICT {label}")

    development_path = audit_item.get("development_path")
    if development_path not in ALLOWED_DEVELOPMENT_PATHS:
        failures.append(f"DEVELOPMENT_PATH_INVALID {label}: {development_path}")
    topic_form = audit_item.get("topic_form")
    if topic_form not in ALLOWED_TOPIC_FORMS:
        failures.append(f"TOPIC_FORM_INVALID {label}: {topic_form}")
    elif topic_form == "open_question" and not title.endswith(("？", "?")):
        failures.append(f"OPEN_QUESTION_WITHOUT_QUESTION_MARK {label}")
    elif topic_form == "directional_hypothesis" and title.endswith(("？", "?")):
        failures.append(f"DIRECTIONAL_HYPOTHESIS_AS_QUESTION {label}")

    relation = field_value(block, "生成关系") or ""
    if len(semantic_text(relation)) < 14 or "保留" not in relation:
        failures.append(f"GENERATION_RELATION_TOO_VAGUE {label}")
    if "来自数据库" in relation and len(semantic_text(relation)) < 30:
        failures.append(f"GENERATION_RELATION_GENERIC {label}")
    for action in actions:
        if not action_mentioned(action, relation):
            failures.append(f"PROCESSING_ACTION_NOT_DISPLAYED {label}: {action}")

    added_elements = audit_item.get("added_elements")
    if not isinstance(added_elements, list):
        failures.append(f"ADDED_ELEMENTS_INVALID {label}")
        added_elements = []
    if actions and actions != ["未加工"] and not added_elements:
        failures.append(f"ADDED_ELEMENT_MISSING {label}")
    if "未加工" in actions and added_elements:
        failures.append(f"UNPROCESSED_WITH_ADDED_ELEMENT {label}")

    allowed_types = set().union(*(ACTION_ELEMENT_TYPES.get(action, set()) for action in actions))
    for index, element in enumerate(added_elements):
        element_label = f"{label} element[{index}]"
        if not isinstance(element, dict):
            failures.append(f"ADDED_ELEMENT_INVALID {element_label}")
            continue
        element_type = element.get("type")
        value = element.get("value")
        basis_quote = element.get("basis_quote")
        basis_source = resolve_recorded_path(element.get("basis_source"), audit_path)
        if not isinstance(element_type, str) or not element_type:
            failures.append(f"ADDED_ELEMENT_TYPE_MISSING {element_label}")
        elif element_type not in allowed_types:
            failures.append(f"ADDED_ELEMENT_TYPE_NOT_ALLOWED {element_label}: {element_type}")
        if not isinstance(value, str) or len(semantic_text(value)) < 2:
            failures.append(f"ADDED_ELEMENT_VALUE_MISSING {element_label}")
        elif value not in title and value not in relation:
            failures.append(f"ADDED_ELEMENT_NOT_VISIBLE {element_label}: {value}")
        elif pool_problem and compact(value) in compact(pool_problem):
            failures.append(f"ADDED_ELEMENT_ALREADY_IN_SOURCE {element_label}: {value}")
        if basis_source is None or basis_source not in allowed_evidence_paths:
            failures.append(f"ADDED_ELEMENT_SOURCE_NOT_ALLOWED {element_label}")
            continue
        if not isinstance(basis_quote, str) or len(semantic_text(basis_quote)) < 4:
            failures.append(f"ADDED_ELEMENT_QUOTE_MISSING {element_label}")
            continue
        if compact(basis_quote) not in compact(evidence_cache.get(basis_source, "")):
            failures.append(f"ADDED_ELEMENT_UNGROUNDED {element_label}: {basis_quote}")

    difference = audit_item.get("difference")
    if not isinstance(difference, str) or len(semantic_text(difference)) < 8:
        failures.append(f"DIFFERENCE_MISSING {label}")
    if pool_problem and actions != ["未加工"] and near_duplicate(title, pool_problem):
        failures.append(f"SOURCE_NEAR_PARAPHRASE {label}")
    for field in REQUIRED_QUALITY_FIELDS:
        value = audit_item.get(field)
        if not isinstance(value, str) or len(semantic_text(value)) < 6:
            failures.append(f"QUALITY_FIELD_MISSING {label}: {field}")
    verdicts = audit_item.get("verdicts")
    if not isinstance(verdicts, dict):
        failures.append(f"VERDICTS_INVALID {label}")
    else:
        for key in REQUIRED_VERDICTS:
            if verdicts.get(key) is not True:
                failures.append(f"VERDICT_NOT_PASSED {label}: {key}")
    reasons = audit_item.get("reasons")
    if not isinstance(reasons, dict):
        failures.append(f"REASONS_INVALID {label}")
    else:
        for key in REQUIRED_REASONS:
            value = reasons.get(key)
            if not isinstance(value, str) or len(semantic_text(value)) < 6:
                failures.append(f"REASON_MISSING {label}: {key}")


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    if args.count < 1:
        failures.append("COUNT_INVALID: --count must be at least 1")
    for label, path in (("FILE", args.path), ("AUDIT", args.audit), ("PROBLEM_POOL", args.problem_pool)):
        if not path.is_file():
            failures.append(f"{label}_MISSING: {path}")
    if failures:
        print("VALIDATION_FAILED")
        print("\n".join(failures))
        return 1

    text = args.path.read_text(encoding="utf-8")
    for heading in LEGACY_GROUP_HEADINGS:
        if re.search(rf"^##\s+{re.escape(heading)}(?:｜\d+条)?\s*$", text, re.MULTILINE):
            failures.append(f"LEGACY_GROUPED_FORMAT: {heading}")
    blocks = topic_blocks(text)
    if len(blocks) != args.count:
        failures.append(f"COUNT_MISMATCH: expected {args.count}, got {len(blocks)}")
    numbers = [number for number, _, _ in blocks]
    expected = list(range(1, args.count + 1))
    if numbers != expected:
        failures.append(f"NUMBERING_INVALID: expected {expected}, got {numbers}")

    problem_data = load_json(args.problem_pool, "PROBLEM_POOL", failures)
    problems = problem_records(problem_data, failures) if problem_data is not None else {}
    audit_data = load_json(args.audit, "AUDIT", failures)
    if not isinstance(audit_data, dict):
        audit_data = {}
    if audit_data.get("schema_version") != "topic-candidate-audit-v3":
        failures.append(f"AUDIT_SCHEMA_INVALID: {audit_data.get('schema_version')}")
    if audit_data.get("calibration_state") != "ready":
        failures.append(f"CALIBRATION_NOT_READY: {audit_data.get('calibration_state')}")
    calibration = audit_data.get("calibration_basis")
    if not isinstance(calibration, dict):
        failures.append("CALIBRATION_BASIS_INVALID")
    else:
        if calibration.get("confirmed_by_user") is not True:
            failures.append("CALIBRATION_NOT_USER_CONFIRMED")
        if not isinstance(calibration.get("target_audience"), str) or len(
            semantic_text(calibration.get("target_audience", ""))
        ) < 2:
            failures.append("CALIBRATION_TARGET_AUDIENCE_MISSING")
        for field in ("confirmed_rules", "positive_examples", "negative_examples"):
            values = calibration.get(field)
            if not isinstance(values, list) or not values or any(
                not isinstance(item, str) or len(semantic_text(item)) < 4 for item in values
            ):
                failures.append(f"CALIBRATION_FIELD_INVALID: {field}")
    audit_mode = audit_data.get("topic_mode")
    if audit_mode != args.mode:
        failures.append(f"TOPIC_MODE_MISMATCH: cli={args.mode} audit={audit_mode}")
    allowed_raw = audit_data.get("allowed_source_problem_ids")
    if not isinstance(allowed_raw, list) or not allowed_raw or any(
        not isinstance(item, str) or item not in problems for item in allowed_raw
    ):
        failures.append("ALLOWED_SOURCE_PROBLEMS_INVALID")
        allowed_problem_ids: set[str] = set()
    else:
        allowed_problem_ids = set(allowed_raw)
        if len(allowed_problem_ids) != len(allowed_raw):
            failures.append("ALLOWED_SOURCE_PROBLEMS_DUPLICATE")

    if args.mode == "single_source":
        if len(allowed_problem_ids) != 1:
            failures.append("SINGLE_SOURCE_PROBLEM_COUNT_INVALID")
        single_record = audit_data.get("single_source_record_id")
        if not isinstance(single_record, str) or not single_record.strip():
            failures.append("SINGLE_SOURCE_RECORD_MISSING")
        elif allowed_problem_ids:
            only_problem = problems[next(iter(allowed_problem_ids))]
            if single_record not in only_problem.get("source_record_ids", []):
                failures.append("SINGLE_SOURCE_RECORD_UNTRACEABLE")
        if "题源范围：单篇题源共创｜围绕这一篇拆出的赛道问题继续加工，不代表赛道已经验证。" not in text:
            failures.append("SINGLE_SOURCE_SCOPE_NOTICE_MISSING")
    else:
        if "单篇题源共创" in text:
            failures.append("TRACK_POOL_WITH_SINGLE_SOURCE_NOTICE")
        distinct_records = {
            record_id
            for problem_id in allowed_problem_ids
            for record_id in problems[problem_id].get("source_record_ids", [])
        }
        if len(allowed_problem_ids) < 2 and len(distinct_records) < 2:
            failures.append("TRACK_POOL_SCOPE_INSUFFICIENT")
    recorded_pool = resolve_recorded_path(audit_data.get("problem_pool_file"), args.audit)
    if recorded_pool != args.problem_pool.resolve():
        failures.append("AUDIT_PROBLEM_POOL_MISMATCH")
    task_path = resolve_recorded_path(audit_data.get("current_task_file"), args.audit)
    if task_path is not None and not task_path.is_file():
        failures.append(f"CURRENT_TASK_FILE_MISSING: {task_path}")

    allowed_paths = {args.problem_pool.resolve()}
    if task_path is not None:
        allowed_paths.add(task_path)
    evidence_cache: dict[Path, str] = {}
    for evidence_path in allowed_paths:
        try:
            evidence_cache[evidence_path] = evidence_path.read_text(encoding="utf-8")
        except OSError as error:
            failures.append(f"EVIDENCE_READ_ERROR: {evidence_path}: {error}")

    audit_candidates = audit_data.get("candidates")
    if not isinstance(audit_candidates, list):
        failures.append("AUDIT_CANDIDATES_INVALID")
        audit_candidates = []
    if len(audit_candidates) != args.count:
        failures.append(f"AUDIT_COUNT_MISMATCH: expected {args.count}, got {len(audit_candidates)}")

    for index, (number, title, block) in enumerate(blocks):
        label = f"[{number}] {title}"
        audit_item = audit_candidates[index] if index < len(audit_candidates) else {}
        topic_form = audit_item.get("topic_form") if isinstance(audit_item, dict) else None
        if topic_form == "open_question" and any(pattern.search(title) for pattern in ANSWER_LEAK_PATTERNS):
            failures.append(f"ANSWER_LEAK_IN_TOPIC {label}")
        for field in REQUIRED_FIELDS:
            if not field_value(block, field):
                failures.append(f"FIELD_MISSING {label}: {field}")
        suggestion = field_value(block, "建议") or ""
        if suggestion and not any(marker in suggestion for marker in SUGGESTION_MARKERS):
            failures.append(f"SUGGESTION_NOT_CANDIDATE_TONE {label}")
        source = field_value(block, "来源") or ""
        links = markdown_links(source)
        if not links and "http://" not in source and "https://" not in source:
            failures.append(f"SOURCE_NOT_DIRECT {label}")
        elif links and not any(local_link_exists(link, args.path) for link in links):
            failures.append(f"SOURCE_LINK_UNRESOLVABLE {label}")
        if IDENTITY_RESULT_PATTERN.search(title) and not any(marker in title for marker in THIRD_PARTY_MARKERS):
            failures.append(f"IDENTITY_RESULT_NOT_OWNED {label}")
        if index < len(audit_candidates):
            validate_audit_candidate(
                audit_candidates[index], args.audit, number, title, block, problems,
                allowed_problem_ids, allowed_paths, evidence_cache, failures,
            )

    for first_index, (_, first_title, _) in enumerate(blocks):
        for _, second_title, _ in blocks[first_index + 1:]:
            if near_duplicate(first_title, second_title):
                failures.append(f"TOPIC_NEAR_DUPLICATE: {first_title} <> {second_title}")

    if failures:
        print("VALIDATION_FAILED")
        print("\n".join(failures))
        return 1
    print(
        f"VALIDATION_OK {args.count}/{args.count} mode={args.mode} "
        f"source_matched={args.count} semantic_audit={args.count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
