#!/usr/bin/env python3
"""Check packaged resources and discovery; optional runtime by current stage."""
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
PROJECT_SKILLS = Path(__file__).resolve().parents[2]
GLOBAL_SKILLS = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills"
DEPENDENCIES = ("jiangdao-adapt-topic", "jiangdao-deconstruct", "jiangdao-produce", "jiangdao-review", "jiangdao-transcribe", "jiangdao-edit", "jiangdao-publish", "jiangdao-dialogue-partner")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

def linked_resources(entrypoints: list[Path]) -> tuple[set[Path], list[str]]:
    """Recursively resolve local Markdown links from active entrypoints."""

    visited: set[Path] = set()
    queue = list(entrypoints)
    failures: list[str] = []
    while queue:
        current = queue.pop()
        resolved_current = current.resolve()
        if resolved_current in visited or not current.is_file():
            continue
        visited.add(resolved_current)
        if current.suffix.lower() != ".md":
            continue
        text = current.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target_text = raw_target.split("#", 1)[0].strip()
            if not target_text or target_text.startswith(("http://", "https://", "mailto:")):
                continue
            target = (current.parent / target_text).resolve()
            if not target.exists():
                failures.append(f"REFERENCE_MISSING {current}: {target_text}")
                continue
            if target.is_file() and target.suffix.lower() == ".md":
                queue.append(target)
    return visited, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-only', action='store_true', help='Validate bundle before installation; does not claim discovery.')
    parser.add_argument('--global-skills', type=Path, default=GLOBAL_SKILLS)
    parser.add_argument('--stage', choices=['core','douyin','transcribe','edit','full-package','publish'], default='core')
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--platform', choices=['douyin','xiaohongshu','kuaishou','bilibili'])
    args = parser.parse_args()
    failures = []
    entrypoints = [PROJECT_SKILLS/'jiangdao-content/SKILL.md']
    for name in DEPENDENCIES:
        source = PROJECT_SKILLS/name
        installed = args.global_skills/name
        if not (source/'SKILL.md').is_file():
            failures.append('SOURCE_MISSING '+name)
            continue
        if not args.source_only:
            if not (installed/'SKILL.md').is_file():failures.append('GLOBAL_ENTRY_MISSING '+name)
            elif installed.resolve() != source.resolve():failures.append('WRONG_TARGET '+name)
        entrypoints.append(source/'SKILL.md')
    resources, broken = linked_resources(entrypoints)
    failures.extend(broken)
    runtime = PROJECT_SKILLS/'shared/scripts/check-runtime.py'
    if not runtime.is_file():failures.append('RUNTIME_CHECKER_MISSING')
    if failures:
        print('SKILL_DEPENDENCY_MISSING');print('\n'.join(failures));return 1
    print(f"DEPENDENCY_OK {len(DEPENDENCIES)}/{len(DEPENDENCIES)} RESOURCES_OK {len(resources)} DISCOVERY={'not_checked' if args.source_only else 'passed'}", flush=True)
    command = [sys.executable,str(runtime),'--stage',args.stage,'--project',str(args.project),'--global-skills',str(args.global_skills)]
    if args.platform:command.extend(['--platform',args.platform])
    return subprocess.run(command, check=False).returncode
if __name__ == '__main__':
    sys.exit(main())
