#!/usr/bin/env python3
"""Run the formal Douyin downloader and verify acquisition artifacts.

This entrypoint deliberately stops at the acquisition layer. It verifies that
media, metadata, and a comments response were actually written, then emits a
machine-readable report. Content and market readiness remain the responsibility
of check-douyin-sample.py.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'shared/scripts'))
from runtime_config import downloader_path

VIDEO_ID_RE = re.compile(r"/(?:video|note)/(\d+)")
MEDIA_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def nonempty_files(paths: list[Path]) -> list[Path]:
    return sorted(path.resolve() for path in paths if path.is_file() and path.stat().st_size > 0)


def matching_files(output_dir: Path, url: str) -> dict[str, list[Path]]:
    """Find artifacts for one URL in an isolated output directory."""

    match = VIDEO_ID_RE.search(url)
    sample_id = match.group(1) if match else ""
    files = [path for path in output_dir.rglob("*") if path.is_file()]
    if sample_id:
        sample_files = [path for path in files if sample_id in path.name or sample_id in str(path.parent)]
    else:
        sample_files = files

    media = nonempty_files([path for path in sample_files if path.suffix.lower() in MEDIA_SUFFIXES])
    metadata = nonempty_files(
        [path for path in sample_files if path.name.endswith("_data.json")]
    )
    comments = nonempty_files(
        [path for path in sample_files if path.name.endswith("_comments.json")]
    )
    manifests = nonempty_files(
        [path for path in files if path.name == "download_manifest.jsonl"]
    )
    return {
        "media": media,
        "metadata": metadata,
        "comments": comments,
        "manifest": manifests,
    }


def valid_json_files(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    valid: list[Path] = []
    invalid: list[Path] = []
    for path in paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            valid.append(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            invalid.append(path)
    return valid, invalid


def probe_media(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    valid: list[Path] = []
    invalid: list[Path] = []
    for path in paths:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if float(result.stdout.strip()) > 0:
                valid.append(path)
            else:
                invalid.append(path)
        except (OSError, ValueError, subprocess.SubprocessError):
            invalid.append(path)
    return valid, invalid


def make_report(
    url: str,
    output_dir: Path,
    downloader_dir: Path,
    download_exit_code: int,
) -> dict[str, Any]:
    artifacts = matching_files(output_dir, url)
    media_valid, media_invalid = probe_media(artifacts["media"])
    metadata_valid, metadata_invalid = valid_json_files(artifacts["metadata"])
    comments_valid, comments_invalid = valid_json_files(artifacts["comments"])

    artifact_status = {
        "media": "passed" if media_valid else "failed",
        "metadata": "passed" if metadata_valid else "failed",
        "comments": "passed" if comments_valid else "failed",
    }
    if all(status == "passed" for status in artifact_status.values()) and download_exit_code == 0:
        acquisition_state = "completed"
    elif media_valid or metadata_valid or comments_valid:
        acquisition_state = "partial"
    else:
        acquisition_state = "failed"

    blockers = [name + "_missing_or_invalid" for name, status in artifact_status.items() if status != "passed"]
    if download_exit_code != 0:
        blockers.append("downloader_exit_nonzero")

    commit = "unknown"
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=downloader_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    return {
        "url": url,
        "download_exit_code": download_exit_code,
        "acquisition_state": acquisition_state,
        "sample_state": "candidate" if acquisition_state != "failed" else "failed",
        "artifact_status": artifact_status,
        "artifacts": {
            "media": [str(path) for path in media_valid],
            "metadata": [str(path) for path in metadata_valid],
            "comments": [str(path) for path in comments_valid],
            "manifest": [str(path) for path in artifacts["manifest"]],
        },
        "invalid_artifacts": {
            "media": [str(path) for path in media_invalid],
            "metadata": [str(path) for path in metadata_invalid],
            "comments": [str(path) for path in comments_invalid],
        },
        "blockers": sorted(set(blockers)),
        "downloader": {
            "path": str(downloader_dir),
            "commit": commit,
        },
        "next_gate": "check-douyin-sample.py",
    }


def parser() -> argparse.ArgumentParser:
    root = project_root()
    downloader_dir = downloader_path()
    result = argparse.ArgumentParser(description="Collect and verify one Douyin URL")
    result.add_argument("url")
    result.add_argument("output_dir", type=Path)
    result.add_argument("--downloader-dir", type=Path, default=downloader_dir)
    result.add_argument("--config", type=Path)
    result.add_argument("--report", type=Path)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    downloader_dir = args.downloader_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    config = (args.config or downloader_dir / "config.yml").expanduser().resolve()
    report_path = (args.report or output_dir / "acquisition-report.json").expanduser().resolve()
    python = downloader_dir / ".venv" / "bin" / "python"
    run_py = downloader_dir / "run.py"

    missing = [str(path) for path in (python, run_py, config) if not path.is_file()]
    if missing:
        print(json.dumps({"error": "FORMAL_DOWNLOADER_MISSING", "missing": missing}, ensure_ascii=False))
        return 3

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(python),
        str(run_py),
        "-c",
        str(config),
        "-u",
        args.url,
        "-p",
        str(output_dir),
        "--show-warnings",
    ]
    completed = subprocess.run(command, cwd=downloader_dir, check=False)
    report = make_report(args.url, output_dir, downloader_dir, completed.returncode)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    report_path.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)

    if report["acquisition_state"] == "completed":
        return 0
    if report["acquisition_state"] == "partial":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
