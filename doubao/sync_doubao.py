#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_jiangdao_doubao.py —— 江导 Skills 豆包版同步脚本

用途
  从 GitHub 仓库抓取「江导 Skills」发布包，自动识别豆包版并安装到豆包技能根目录。
  每次仓库更新后运行本脚本，即可完成：拉取 → 校验 → 版本比对 → 数据快照 →
  备份旧版 → 替换 → 回归检查 的完整预处理流程。

豆包版识别约定（按优先级自动探测，你发布豆包版时三选一）：
  1. 仓库内 doubao/ 子目录 + 其内 release-manifest.json
  2. 仓库根目录 doubao-manifest.json
  3. 根 release-manifest.json 内包含 "doubao" 字段
  若都未找到，且指定了 --fallback-adapt，则用普通版做适配安装（标记为转换版）。

用法
  python3 sync_jiangdao_doubao.py status                      # 查看本地安装状态
  python3 sync_jiangdao_doubao.py check [--dry-run]           # 检查远程是否有新版（不安装）
  python3 sync_jiangdao_doubao.py sync [--dry-run]            # 完整同步（默认入口）
  python3 sync_jiangdao_doubao.py rollback                    # 回滚到最近一次备份

常用参数
  --dest <目录>          安装目标（默认自动探测豆包 .user_skills 根）
  --repo <owner/repo>    仓库（默认 CAPTAINJJJF/jiangdao-skills）
  --branch <分支>        分支（默认 main）；也可用 --tag <版本> 指定 tag
  --fallback-adapt       豆包版未发布时，用普通版适配安装
  --bundle <目录或ZIP>    使用本地候选，不访问远端
  --dry-run              只演练，不修改安装、备份和同步状态（可创建临时目录）

安全保证
  - 不触碰 ~/.config/jiangdao/runtime.json 及人格库/下载器等用户数据（只做哈希快照记录）
  - 安装前自动备份旧版到 ~/.config/jiangdao/backups/，可随时 rollback
  - 安装采用「先移旧、再复制、失败即恢复」策略，不覆盖写入
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

REPO_DEFAULT = "CAPTAINJJJF/jiangdao-skills"
BRANCH_DEFAULT = "main"
CONFIG_DIR = Path(os.environ.get("JIANGDAO_SYNC_CONFIG_DIR", str(Path.home() / ".config" / "jiangdao"))).expanduser()
BACKUP_DIR = CONFIG_DIR / "backups"
STATE_FILE = CONFIG_DIR / "doubao-sync-state.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) sync-jiangdao-doubao/1.0"

# 豆包技能根目录的候选探测路径（Mac 豆包客户端默认位置）
DEST_CANDIDATES = [
    Path.home() / "Library/Application Support/Doubao/Default/.doubao/agent_mode/workspace/.user_skills",
    Path.home() / "Library/Application Support/Doubao/Default/.doubao/agent_mode/workspace/.skills",
    Path.home() / "Doubao/skills",
]


# ---------------------------------------------------------------- 基础工具

def log(msg: str) -> None:
    print(msg, flush=True)


def err(msg: str) -> None:
    print("ERROR: " + msg, file=sys.stderr, flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def default_dest() -> Path | None:
    env = os.environ.get("DOUBAO_SKILLS_DIR")
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p
    for c in DEST_CANDIDATES:
        if c.is_dir():
            return c
    return None


def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------- 拉取与解压

def download_zip(repo: str, branch: str | None, tag: str | None, tmp: Path) -> Path:
    if tag:
        url = f"https://github.com/{repo}/archive/refs/tags/{tag}.zip"
    else:
        url = f"https://github.com/{repo}/archive/refs/heads/{branch or BRANCH_DEFAULT}.zip"
    log(f"下载发布包: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    dest = tmp / "bundle.zip"
    try:
        with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        raise RuntimeError(f"下载失败: {e}（请检查网络或仓库地址）")
    return dest


def extract_zip(zip_path: Path, tmp: Path) -> Path:
    out = tmp / "src"
    with zipfile.ZipFile(zip_path) as z:
        seen = set()
        for info in z.infolist():
            parts = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (parts.is_absolute() or '..' in parts.parts or '\\' in info.filename
                    or (parts.parts and ':' in parts.parts[0]) or mode & 0o170000 == 0o120000
                    or info.filename in seen):
                raise RuntimeError("Unsafe archive member")
            seen.add(info.filename)
        z.extractall(out)
    entries = list(out.iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        raise RuntimeError("发布包结构异常：未找到唯一根目录")
    return entries[0]


# ---------------------------------------------------------------- 豆包版识别

def find_doubao_manifest(root: Path) -> tuple[Path | None, Path | None, str | None]:
    """返回 (manifest_path, base_dir, kind)。kind 用于状态记录。"""
    p1 = root / "doubao" / "release-manifest.json"
    if p1.is_file():
        return p1, root / "doubao", "doubao-dir"
    p2 = root / "doubao-manifest.json"
    if p2.is_file():
        return p2, root, "doubao-root"
    p3 = root / "release-manifest.json"
    if p3.is_file():
        try:
            data = json.loads(p3.read_text(encoding="utf-8"))
            if isinstance(data.get("doubao"), dict):
                return p3, root, "doubao-inline"
        except Exception:
            pass
    return None, None, None


# ---------------------------------------------------------------- 校验

def verify_manifest(base: Path, manifest_data: dict) -> list[str]:
    errors = []
    expected = manifest_data.get("files")
    skills = manifest_data.get("skills")
    if not isinstance(expected, dict) or not expected or not isinstance(skills, list) or not skills:
        return ["manifest 缺少 files 或 skills"]
    if (len(skills) != len(set(skills)) or any(not isinstance(n, str) or not re.fullmatch(r'jiangdao-[a-z0-9-]+', n) for n in skills)
            or set(skills) & {'jiangdao-product', 'jiangdao-live-clip-selector'}):
        return ["INVALID_SKILL_ROOTS"]
    if not (base / 'shared').is_dir():errors.append('MISSING shared')
    for skill in skills:
        if skill + '/SKILL.md' not in expected:errors.append('MISSING_ENTRY '+skill)
    for name, digest in expected.items():
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or '..' in path.parts or '\\' in name
                or ':' in path.parts[0] or not re.fullmatch('[a-f0-9]{64}', str(digest))):
            errors.append('INVALID_PATH_OR_DIGEST '+name);continue
        if any((base.joinpath(*path.parts[:i])).is_symlink() for i in range(1,len(path.parts)+1)):
            errors.append('SYMLINK '+name);continue
        file = base / name
        if not file.is_file():errors.append('MISSING '+name)
        elif sha256_file(file) != digest:errors.append('DIGEST_MISMATCH '+name)
    allowed = {'release-manifest.json','doubao-manifest.json','CHANGELOG.md','README.md','LICENSE','.gitignore'}
    for file in base.rglob('*'):
        name = file.relative_to(base).as_posix()
        if file.is_symlink():errors.append('SYMLINK '+name)
        elif file.is_file() and name not in expected and name not in allowed:
            errors.append('UNLISTED '+name)
    return errors


def load_manifest(manifest_path: Path) -> dict:
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"manifest 解析失败: {e}")


# ---------------------------------------------------------------- 差异与备份

def installed_names(dest: Path, skills: list[str]) -> list[str]:
    return [*skills, "shared"]


def diff_against_state(manifest_data: dict, state: dict) -> dict:
    remote_files = manifest_data.get("files", {})
    local_files = state.get("files", {})
    changed = [k for k in remote_files if local_files.get(k) != remote_files[k]]
    added = [k for k in remote_files if k not in local_files]
    removed = [k for k in local_files if k not in remote_files]
    return {"changed": sorted(changed), "added": sorted(added), "removed": sorted(removed)}


def backup_installed(dest: Path, names: list[str], version: str) -> Path | None:
    targets = [n for n in names if (dest / n).exists() or (dest / n).is_symlink()]
    if not targets:return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bk = Path(tempfile.mkdtemp(prefix='snapshot-', dir=BACKUP_DIR))
    try:
        for name in targets:shutil.move(str(dest/name), str(bk/name))
    except BaseException:
        for item in list(bk.iterdir()):shutil.move(str(item), str(dest/item.name))
        bk.rmdir()
        raise
    log(f"已备份旧版 {len(targets)} 个目录")
    return bk


# ---------------------------------------------------------------- 安装

def install_bundle(base: Path, names: list[str], dest: Path, dry_run: bool) -> None:
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    for n in names:
        src = base / n
        if not src.is_dir():
            raise RuntimeError(f"发布包缺少目录: {n}")
        tgt = dest / n
        if dry_run:
            log(f"[演练] 将安装 {n} → {tgt}")
            continue
        shutil.copytree(src, tgt, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        log(f"已安装 {n}")


# ---------------------------------------------------------------- 回归检查

def verify_install(dest: Path, names: list[str]) -> list[str]:
    problems: list[str] = []
    for n in names:
        if n == "shared":
            if not (dest / n).is_dir():
                problems.append("shared: 目录缺失")
            continue
        smd = dest / n / "SKILL.md"
        if not smd.is_file():
            problems.append(f"{n}: 缺少 SKILL.md")
            continue
        text = smd.read_text(encoding="utf-8", errors="replace")[:2000]
        m = re.search(r"^---\s*\n(.*?)\n---", text, re.S)
        if not m:
            problems.append(f"{n}: SKILL.md 缺少 frontmatter")
        else:
            fm = m.group(1)
            if not re.search(r"^name\s*:", fm, re.M):
                problems.append(f"{n}: frontmatter 缺少 name")
            if not re.search(r"^description\s*:", fm, re.M):
                problems.append(f"{n}: frontmatter 缺少 description")
    # 运行仓库自带的环境检查（若安装的 shared 中含 check-runtime.py）
    crt = dest / "shared" / "scripts" / "check-runtime.py"
    if crt.is_file():
        try:
            r = subprocess.run(
                [sys.executable, str(crt), "--stage", "core", "--global-skills", str(dest)],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                problems.append("check-runtime core 未通过: " + (r.stdout + r.stderr).strip()[:300])
        except Exception as e:
            problems.append(f"check-runtime 执行失败: {e}")
    return problems


# ---------------------------------------------------------------- 主流程

def cmd_status(args) -> int:
    dest = args.dest or default_dest()
    if not dest:
        err("未找到豆包技能根目录，请用 --dest 指定")
        return 1
    state = load_state()
    log(f"安装目标: {dest}")
    if state:
        log(f"上次同步: 版本 {state.get('version')} ({state.get('kind')})，时间 {state.get('synced_at')}")
    else:
        log("上次同步: 无记录（尚未执行过 sync）")
    installed = sorted([p.name for p in dest.iterdir() if p.is_dir() and p.name.startswith("jiangdao-")])
    if installed:
        log(f"当前已装 jiangdao skill ({len(installed)}):")
        for n in installed:
            log(f"  - {n}")
    else:
        log("当前未安装任何 jiangdao skill")
    return 0


def prepare_bundle(args) -> tuple:
    tmp = Path(tempfile.mkdtemp(prefix='jiangdao-sync-'))
    workdir = None
    try:
        bundle = getattr(args, 'bundle', None)
        if bundle:
            bundle = Path(bundle).expanduser().resolve()
            root = bundle if bundle.is_dir() else extract_zip(bundle, tmp)
        else:
            root = extract_zip(download_zip(args.repo,args.branch,args.tag,tmp),tmp)
        mpath, mbase, kind = find_doubao_manifest(root)
        if mpath is None:
            if not args.fallback_adapt:
                raise RuntimeError('未找到豆包版发布清单；请先构建双版本候选包。')
            mpath, mbase, kind = root/'release-manifest.json', root, 'adapted'
        manifest = load_manifest(mpath)
        if kind == 'doubao-inline':manifest = manifest['doubao']
        errors = verify_manifest(mbase, manifest)
        if errors:raise RuntimeError('发布包校验失败:\n'+'\n'.join(errors[:30]))
        if kind == 'doubao-dir' and any((mbase/n/'agents/openai.yaml').exists() for n in manifest['skills']):
            raise RuntimeError('CODEX_METADATA_IN_DOUBAO')
        workdir = Path(tempfile.mkdtemp(prefix='jiangdao-bundle-'))
        for name in [*manifest['skills'],'shared']:
            shutil.copytree(mbase/name,workdir/name)
            if kind == 'adapted':
                (workdir/name/'agents/openai.yaml').unlink(missing_ok=True)
        log(f"校验通过: version={manifest['version']} kind={kind} skills={len(manifest['skills'])}")
        return workdir, manifest, mpath, str(manifest['version']), kind, None
    except BaseException:
        if workdir:shutil.rmtree(workdir,ignore_errors=True)
        raise
    finally:shutil.rmtree(tmp,ignore_errors=True)


def cmd_check(args) -> int:
    workdir = None
    try:
        workdir, manifest, _, version, kind, _ = prepare_bundle(args)
        state = load_state(); diff = diff_against_state(manifest,state)
        if state.get('version') == version and state.get('kind') == kind and not any(diff.values()):
            log('本地已是最新，无需同步。')
        else:log(f"发现更新: {version} ({kind})，变更 {len(diff['changed'])}、新增 {len(diff['added'])}、删除 {len(diff['removed'])}。")
        return 0
    except (RuntimeError,OSError,ValueError) as e:err(str(e));return 1
    finally:
        if workdir:shutil.rmtree(workdir,ignore_errors=True)


def cmd_sync(args) -> int:
    dest = args.dest or default_dest()
    if not dest:err('未找到豆包技能根目录，请用 --dest 指定');return 1
    dest = Path(dest).expanduser().absolute()
    state = load_state(); workdir = backup = None
    names = []; writing = False
    try:
        workdir, manifest, _, version, kind, _ = prepare_bundle(args)
        names = installed_names(dest,manifest['skills'])
        if dest.is_symlink() or any((dest/n).is_symlink() for n in names):
            raise RuntimeError('安装目标存在符号链接，保留旧目录并停止。')
        diff = diff_against_state(manifest,state)
        same = state.get('version') == version and state.get('kind') == kind and not any(diff.values())
        for name, digest in manifest['files'].items():
            if name.split('/')[0] in names:
                if not (dest/name).is_file() or sha256_file(dest/name) != digest:same = False;break
        if same:log('本地已是最新，跳过安装。');return 0
        problems = verify_install(workdir,names)
        if problems:raise RuntimeError('安装前回归失败: '+'; '.join(problems))
        if args.dry_run:log('演练通过，未修改安装或同步状态。');return 0
        snap = {}; runtime = CONFIG_DIR/'runtime.json'
        if runtime.is_file():snap['runtime_json_sha256'] = sha256_file(runtime)
        backup = backup_installed(dest,names,version)
        writing = True
        install_bundle(workdir,names,dest,False)
        problems = verify_install(dest,names)
        if problems:raise RuntimeError('安装后回归失败: '+'; '.join(problems))
        for name, digest in manifest['files'].items():
            if name.split('/')[0] in names and (kind != 'adapted' or not name.endswith('/agents/openai.yaml')):
                if not (dest/name).is_file() or sha256_file(dest/name) != digest:
                    raise RuntimeError('安装后文件不一致: '+name)
        if runtime.is_file() and snap.get('runtime_json_sha256') != sha256_file(runtime):
            raise RuntimeError('用户配置发生变化，停止记录成功状态。')
        save_state({'version':version,'kind':kind,'source':str(getattr(args,'bundle',None) or f'{args.repo}@{args.tag or args.branch}'),
                    'synced_at':datetime.now().isoformat(timespec='seconds'),'files':manifest['files'],
                    'user_data_snapshot':snap,'last_backup':str(backup) if backup else None,'installed_names':names,'previous_state':state if state else None})
        log('安装与回归通过。请到豆包“技能 · 连接器”→“我的技能”点击“刷新”，再新开工作任务核验实际发现和调用。')
        return 0
    except (RuntimeError,OSError,ValueError) as e:
        err(str(e))
        if writing:
            for name in names:
                target = dest/name
                if target.is_symlink() or target.is_file():target.unlink()
                elif target.is_dir():shutil.rmtree(target)
            if backup:
                _restore_backup(dest,backup)
        return 1
    finally:
        if workdir:shutil.rmtree(workdir,ignore_errors=True)


def _restore_backup(dest: Path, backup_path: Path) -> None:
    restored = []
    for n in backup_path.iterdir():
        tgt = dest / n.name
        if tgt.exists():
            shutil.rmtree(tgt)
        shutil.move(str(n), str(tgt))
        restored.append(n.name)
    log(f"已恢复备份 {backup_path}（{len(restored)} 个目录）")
    leftover = sorted(p.name for p in dest.iterdir()
                      if p.name.startswith("jiangdao-") or p.name == "shared")
    extra = [n for n in leftover if n not in restored]
    if extra:
        log("提示: 以下目录不在该备份中，未被回滚处理: " + ", ".join(extra))


def cmd_rollback(args) -> int:
    dest = args.dest or default_dest(); state = load_state()
    if not dest:err('未找到豆包技能根目录');return 1
    if not state.get('last_backup'):err('没有对应当前安装的回滚备份');return 1
    backup = Path(state['last_backup'])
    if not backup.is_dir() or not backup.resolve().is_relative_to(BACKUP_DIR.resolve()):
        err('回滚备份不可用');return 1
    if args.dry_run:log('可恢复当前安装对应备份');return 0
    for name in state.get('installed_names',[]):
        if not re.fullmatch(r'jiangdao-[a-z0-9-]+|shared',name):raise RuntimeError('Invalid rollback target')
        target = Path(dest)/name
        if target.is_symlink() or target.is_file():target.unlink()
        elif target.is_dir():shutil.rmtree(target)
    _restore_backup(Path(dest),backup)
    if state.get('previous_state'):save_state(state['previous_state'])
    else:STATE_FILE.unlink(missing_ok=True)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="江导 Skills 豆包版同步脚本")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("status", "check", "sync", "rollback"):
        sp = sub.add_parser(name)
        sp.add_argument("--dest", type=Path, default=None, help="安装目标目录（默认自动探测）")
        sp.add_argument("--repo", default=REPO_DEFAULT, help=f"仓库 owner/repo（默认 {REPO_DEFAULT}）")
        sp.add_argument("--branch", default=None, help="分支（默认 main）")
        sp.add_argument("--tag", default=None, help="指定 tag（如 v1.0），与 --branch 二选一")
        sp.add_argument("--bundle", type=Path, help="本地双版本候选目录或 ZIP；不访问远端")
        sp.add_argument("--fallback-adapt", action="store_true", help="豆包版未发布时用普通版适配")
        sp.add_argument("--dry-run", action="store_true", help="只演练，不修改安装与同步状态")
        sp.set_defaults(func={"status": cmd_status, "check": cmd_check, "sync": cmd_sync, "rollback": cmd_rollback}[name])
    args = p.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        err("已中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
