#!/usr/bin/env python3
"""Verify both distributions, their shared source parity, and host-specific omissions."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import sys
from verify_bundle import verify


def verify_dual(root: Path) -> dict:
    root = root.resolve()
    codex = verify(root)
    if codex.get('variants', {}).get('doubao') != 'doubao/release-manifest.json':
        raise ValueError('DOUBAO_VARIANT_REQUIRED')
    doubao = verify(root/'doubao')
    if codex.get('version') != doubao.get('version'):
        raise ValueError('VARIANT_VERSION_MISMATCH')
    for field in ['skills','front_entries','excluded_modules']:
        if codex.get(field) != doubao.get(field):raise ValueError('VARIANT_METADATA_MISMATCH '+field)
    if set(codex['excluded_modules']) != {'jiangdao-product','jiangdao-live-clip-selector'}:
        raise ValueError('EXCLUDED_MODULE_SCOPE_CHANGED')
    if len(codex['skills']) != 15:raise ValueError('PUBLIC_SKILL_SCOPE_CHANGED')
    namespaces = set(codex['skills']) | {'shared'}
    def selected(files):
        return {n:d for n,d in files.items() if n.split('/')[0] in namespaces}
    first = selected(codex['files']); second = selected(doubao['files'])
    omitted = {n for n in first if n.endswith('/agents/openai.yaml')}
    if set(second) != set(first)-omitted:raise ValueError('VARIANT_FILESET_MISMATCH')
    for name,digest in second.items():
        if first[name] != digest:raise ValueError('VARIANT_CONTENT_DRIFT '+name)
    for base,data in [(root,codex),(root/'doubao',doubao)]:
        for name in data['excluded_modules']:
            if (base/name).exists():raise ValueError('INTERNAL_MODULE_INCLUDED '+name)
        for name in data['skills']:
            text=(base/name/'SKILL.md').read_text()
            fm=re.match(r'^---\s*\n(.*?)\n---',text,re.S)
            if not fm or not re.search(r'^name:\s*'+re.escape(name)+r'\s*$',fm[1],re.M) or not re.search(r'^description:\s*\S',fm[1],re.M):
                raise ValueError('SKILL_FRONTMATTER_INVALID '+name)
            match=re.search(r'^  version:\s*["\x27]?([0-9]+(?:\.[0-9]+){1,2})',fm[1],re.M)
            if not match or match[1] != str(data['version']):raise ValueError('SKILL_VERSION_MISMATCH '+name)
    return {'status':'passed','version':codex['version'],'codex_skills':len(codex['skills']),
            'doubao_skills':len(doubao['skills']),'same_source_files':len(second),'omitted_codex_metadata':len(omitted),
            'manifest_sha256':hashlib.sha256((root/'release-manifest.json').read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path,nargs='?',default=Path(__file__).resolve().parent);a=p.parse_args()
    try:print(verify_dual(a.bundle))
    except (ValueError,OSError,KeyError) as e:print(str(e),file=sys.stderr);sys.exit(1)
