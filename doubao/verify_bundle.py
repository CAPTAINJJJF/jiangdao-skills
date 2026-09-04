#!/usr/bin/env python3
"""Verify exact release inventory and content digests, with no network calls."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def verify(root: Path) -> dict:
    root = root.resolve()
    data = json.loads((root/'release-manifest.json').read_text(encoding='utf-8'))
    expected = data['files']
    errors = []
    for name, digest in expected.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name:
            errors.append('INVALID_PATH '+name);continue
        p = root/name
        if any((root.joinpath(*path.parts[:i])).is_symlink() for i in range(1,len(path.parts)+1)):
            errors.append('SYMLINK '+name);continue
        if not p.is_file():errors.append('MISSING '+name);continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != digest:errors.append('DIGEST_MISMATCH '+name)
    actual = set()
    for p in root.rglob('*'):
        if p.relative_to(root).parts[0] == '.git' or '__pycache__' in p.parts or p.name == '.DS_Store':continue
        if p.is_symlink():errors.append('SYMLINK '+str(p.relative_to(root)))
        if p.is_file():actual.add(p.relative_to(root).as_posix())
    for name in sorted(actual-set(expected)-{'release-manifest.json'}):errors.append('UNLISTED '+name)
    for name in expected:
        if name.endswith('.md') and (root/name).is_file():
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',(root/name).read_text(encoding='utf-8')):
                target=target.split('#')[0]
                if not target or target.startswith(('http:','https:','mailto:')):continue
                dest=(root/name).parent/target
                if target.startswith('/') or not dest.resolve().is_relative_to(root) or not dest.exists():errors.append('REFERENCE_INVALID '+name+': '+target)
    if errors:raise ValueError('\n'.join(errors))
    return data

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path,nargs='?',default=Path(__file__).resolve().parent);a=p.parse_args()
    try:
        d=verify(a.bundle);print(f"BUNDLE_OK files={len(d['files'])} skills={len(d['skills'])} version={d['version']}")
    except (OSError,ValueError,KeyError) as e:print(str(e),file=sys.stderr);sys.exit(1)
