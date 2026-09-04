import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).with_name("collect-douyin.py")
SPEC = importlib.util.spec_from_file_location("collect_douyin", SCRIPT)
assert SPEC and SPEC.loader
collect_douyin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect_douyin)


def test_matching_files_is_scoped_to_video_id(tmp_path: Path):
    wanted = tmp_path / "author" / "767123"
    other = tmp_path / "author" / "999999"
    wanted.mkdir(parents=True)
    other.mkdir(parents=True)
    (wanted / "clip_767123.mp4").write_bytes(b"media")
    (wanted / "clip_767123_data.json").write_text("{}", encoding="utf-8")
    (wanted / "clip_767123_comments.json").write_text("{}", encoding="utf-8")
    (other / "clip_999999_data.json").write_text("{}", encoding="utf-8")

    result = collect_douyin.matching_files(tmp_path, "https://www.douyin.com/video/767123")

    assert len(result["media"]) == 1
    assert len(result["metadata"]) == 1
    assert len(result["comments"]) == 1
    assert all("999999" not in str(path) for paths in result.values() for path in paths)


def test_invalid_json_is_separated(tmp_path: Path):
    valid = tmp_path / "valid.json"
    invalid = tmp_path / "invalid.json"
    valid.write_text(json.dumps({"ok": True}), encoding="utf-8")
    invalid.write_text("{", encoding="utf-8")

    passed, failed = collect_douyin.valid_json_files([valid, invalid])

    assert passed == [valid]
    assert failed == [invalid]
