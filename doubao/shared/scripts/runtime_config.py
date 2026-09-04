"""Load user-owned runtime locations; never bundle credentials or personal paths."""
from __future__ import annotations
import json
import os
from pathlib import Path


def skill_root() -> Path:
    """Resolve the current package, without borrowing another host's installation."""
    explicit = os.environ.get('JIANGDAO_SKILLS_DIR') or os.environ.get('DOUBAO_SKILLS_DIR')
    if explicit:
        return Path(explicit).expanduser().resolve()
    current = Path(__file__).resolve()
    codex = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))) / 'skills'
    registered = codex/'shared/scripts/runtime_config.py'
    # A developer installation can symlink this exact package into Codex.
    # Keep its sibling external skills available, but never borrow another copy.
    if registered.is_file() and registered.resolve() == current:
        return codex.absolute()
    return current.parents[2]


def load_config(project: Path | None = None) -> tuple[dict, Path | None]:
    explicit = os.environ.get('JIANGDAO_RUNTIME_CONFIG')
    project = (project or Path.cwd()).resolve()
    candidates = [Path(explicit).expanduser()] if explicit else [project / 'config/jiangdao-runtime.json', Path.home() / '.config/jiangdao/runtime.json']
    for path in candidates:
        if path.is_file():
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema_version') != 1:
                raise ValueError('Runtime config must be an object with schema_version=1')
            return data, path.resolve()
    if explicit:
        raise FileNotFoundError('JIANGDAO_RUNTIME_CONFIG does not name a readable file')
    return {}, None


def configured_path(key: str, project: Path | None = None) -> Path | None:
    data, source = load_config(project)
    value = data.get(key)
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError(f'{key} must be a path string')
    path = Path(value).expanduser()
    return (path if path.is_absolute() else source.parent / path).resolve()


def downloader_path(project: Path | None = None) -> Path:
    explicit = os.environ.get('JIANGDAO_DOUYIN_DOWNLOADER')
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = configured_path('douyin_downloader', project)
    return configured or ((project or Path.cwd()).resolve() / 'tools/douyin-downloader')
