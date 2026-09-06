#!/usr/bin/env python3
"""Read-only, stage-specific capability checks. Never install or log in."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from runtime_config import configured_path, downloader_path, skill_root

COMMIT = '203c1ae078bb3cc1d47f36672ac126e5cf80dee3'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=['core','douyin','transcribe','edit','full-package','publish'], default='core')
    p.add_argument('--project', type=Path, default=Path.cwd())
    p.add_argument('--platform', choices=['douyin','xiaohongshu','kuaishou','bilibili'])
    p.add_argument('--global-skills', type=Path, default=skill_root())
    args = p.parse_args()
    missing = []; notes = []
    def command(name):
        if not shutil.which(name): missing.append('COMMAND_MISSING '+name)
    def skill(name):
        if not (args.global_skills/name/'SKILL.md').is_file():missing.append('EXTERNAL_SKILL_MISSING '+name)
    if sys.version_info < (3,10):missing.append('PYTHON_3_10_REQUIRED')
    if args.stage == 'core':
        command('node')
        notes.append('File and tool presence only; no conversation quality claim.')
    if args.stage == 'douyin':
        d = downloader_path(args.project)
        for name in ['run.py','config.yml','.venv/bin/python','LICENSE']:
            if not (d/name).is_file():missing.append('DOUYIN_COLLECTOR_MISSING '+name)
        try:
            result = subprocess.run(['git','-C',str(d),'rev-parse','HEAD'],capture_output=True,text=True,timeout=10)
            if result.returncode or result.stdout.strip() != COMMIT:missing.append('DOUYIN_COLLECTOR_VERSION_MISMATCH')
        except (OSError,subprocess.TimeoutExpired):missing.append('DOUYIN_COLLECTOR_VERSION_UNREADABLE')
        command('ffprobe')
        notes.append('Credentials not read or tested. Media acquisition still requires a real sample.')
    if args.stage == 'transcribe':
        if platform.system() != 'Darwin' or platform.machine() != 'arm64':missing.append('APPLE_SILICON_REQUIRED')
        for c in ['ffmpeg','ffprobe','uv','node']:command(c)
        notes.append('Model/environment is prepared on first use by run-local-asr.sh; actual transcription not tested.')
    if args.stage in ['edit','full-package']:
        skill('course-cut-review')
        notes.append('Choose the editing route, then verify ChatCut/Jianying/version/export by a real representative sample.')
    if args.stage == 'full-package':
        d=configured_path('motion_style_library',args.project)
        for name in ['WORKFLOW.md','catalog.json','selector/index.html','scripts/serve_selector.py']:
            if not d or not (d/name).is_file():missing.append('MOTION_STYLE_LIBRARY_MISSING '+name)
        notes.append('Current-task notification and user-confirmed motion_style_id remain mandatory; this check does not replace them.')
    if args.stage == 'publish':
        if not args.platform:missing.append('PLATFORM_REQUIRED')
        else:skill(args.platform+'-upload')
        notes.append('Publication requires task-specific authorization and real result verification.')
    print(json.dumps({'stage':args.stage,'status':'ready_for_task_preflight' if not missing else 'missing_dependencies','missing':missing,'notes':notes},ensure_ascii=False,indent=2))
    return bool(missing)
if __name__ == '__main__':
    try:sys.exit(main())
    except (ValueError,OSError) as e:
        print(json.dumps({'status':'configuration_error','error_type':type(e).__name__}));sys.exit(1)
