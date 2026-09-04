#!/usr/bin/env python3
"""Install a verified bundle without overwriting any existing skill/shared folder."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile
from verify_bundle import verify


def install(bundle: Path, destination: Path, check_only: bool = False):
    data=verify(bundle)
    names=[*data['skills'],'shared']
    if len(set(names)) != len(names) or any('/' in n or '\\' in n or n in ['.','..',''] for n in names):raise ValueError('Invalid installation roots')
    for name in names:
        if not (bundle/name).is_dir():raise ValueError('Missing installation root: '+name)
        if (destination/name).exists() or (destination/name).is_symlink():raise FileExistsError('Destination already exists: '+str(destination/name))
    if check_only:
        print('INSTALL_PREFLIGHT_OK (no files written)');return
    destination.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.jiangdao-stage-',dir=destination));created=[]
    try:
        for name in names:
            shutil.copytree(bundle/name,staging/name,ignore=shutil.ignore_patterns('__pycache__','.DS_Store'))
        for name in names:
            # mkdir is an exclusive reservation, including protection against broken symlinks.
            target=destination/name;target.mkdir();created.append(target)
            shutil.copytree(staging/name,target,dirs_exist_ok=True)
    except BaseException:
        for target in reversed(created):shutil.rmtree(target)
        raise
    finally:shutil.rmtree(staging)
    print(f'INSTALLED skills={len(data["skills"])} shared=1 destination={destination}')
    print('Open a new task to discover the installed skills. Existing sessions may retain older instructions.')

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--dest',type=Path,default=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills');p.add_argument('--check',action='store_true');a=p.parse_args()
    try:install(Path(__file__).resolve().parent,a.dest.expanduser().absolute(),a.check)
    except (OSError,ValueError,KeyError) as e:print(str(e),file=sys.stderr);sys.exit(1)
