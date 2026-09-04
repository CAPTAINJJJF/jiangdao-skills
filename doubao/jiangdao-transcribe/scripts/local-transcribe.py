#!/usr/bin/env python3
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import mlx_whisper


DEFAULT_PROMPT = (
    "江导，IP 加 AI，本我分身，操盘手分身，内容编导分身，人格数据库，"
    "赛道与内容数据库，混合二创，爆款，ChatCut，Script Studio。"
)


def media_duration(path: Path) -> float:
    output = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        text=True,
    ).strip()
    return float(output)


def fingerprint(path: Path) -> str:
    stat = path.stat()
    value = f"{path.resolve()}|{stat.st_dev}|{stat.st_ino}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(value.encode()).hexdigest()


def clock(seconds: float, srt: bool = False) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    if srt:
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def read_prompt(terms_file: str) -> str:
    parts = [DEFAULT_PROMPT]
    env_prompt = os.environ.get("JIANGDAO_ASR_INITIAL_PROMPT", "").strip()
    if env_prompt:
        parts.append(env_prompt)
    if terms_file:
        terms = Path(terms_file).read_text(encoding="utf-8").strip()
        if terms:
            parts.append(terms)
    return "\n".join(parts)


def repeated_noise(text: str) -> bool:
    compact = re.sub(r"[\s，。！？、,.!?]", "", text)
    if len(compact) < 16:
        return False
    for size in range(1, min(9, len(compact) // 3) + 1):
        unit = compact[:size]
        repeated = (unit * ((len(compact) // size) + 1))[: len(compact)]
        if sum(a == b for a, b in zip(compact, repeated)) / len(compact) >= 0.9:
            return True
    return False


def normalize_result(raw: dict, duration: float) -> tuple[dict, list[dict]]:
    utterances = []
    filtered = []
    for segment in raw.get("segments", []):
        text = re.sub(r"\s+", " ", str(segment.get("text", "")).strip())
        start = float(segment.get("start", 0) or 0)
        end = float(segment.get("end", 0) or 0)
        reason = None
        if not text:
            reason = "empty_text"
        elif start < 0 or end <= start:
            reason = "invalid_time"
        elif end > duration + 0.75:
            reason = "past_media_end"
        elif repeated_noise(text) and float(segment.get("no_speech_prob", 0) or 0) >= 0.5:
            reason = "probable_silence_hallucination"
        if reason:
            filtered.append({"reason": reason, "start": start, "end": end, "text": text})
            continue

        words = []
        for word in segment.get("words") or []:
            word_text = str(word.get("word", "")).strip()
            word_start = float(word.get("start", start) or start)
            word_end = float(word.get("end", word_start) or word_start)
            if not word_text or word_start < 0 or word_end < word_start or word_end > duration + 0.75:
                continue
            words.append(
                {
                    "text": word_text,
                    "start_time": round(word_start * 1000),
                    "end_time": round(word_end * 1000),
                    "probability": word.get("probability"),
                }
            )
        utterances.append(
            {
                "id": len(utterances),
                "text": text,
                "start_time": round(start * 1000),
                "end_time": round(end * 1000),
                "words": words,
                "avg_logprob": segment.get("avg_logprob"),
                "no_speech_prob": segment.get("no_speech_prob"),
            }
        )
    return {"engine": "mlx-whisper", "language": raw.get("language"), "utterances": utterances}, filtered


def write_text_outputs(output_dir: Path, utterances: list[dict]) -> None:
    plain = "\n\n".join(item["text"] for item in utterances)
    timestamped = "\n".join(
        f"[{clock(item['start_time'] / 1000)} → {clock(item['end_time'] / 1000)}] {item['text']}"
        for item in utterances
    )
    srt = "\n\n".join(
        f"{index}\n{clock(item['start_time'] / 1000, True)} --> "
        f"{clock(item['end_time'] / 1000, True)}\n{item['text']}"
        for index, item in enumerate(utterances, 1)
    )
    (output_dir / "transcript.raw.txt").write_text(f"{plain}\n", encoding="utf-8")
    (output_dir / "transcript.timestamped.txt").write_text(f"{timestamped}\n", encoding="utf-8")
    (output_dir / "transcript.raw.srt").write_text(f"{srt}\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit("用法: local-transcribe.py <媒体> <输出目录> <模型路径或仓库> [专名表]")
    source = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    model_ref = sys.argv[3]
    terms_file = sys.argv[4] if len(sys.argv) > 4 else ""
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = media_duration(source)
    source_fingerprint = fingerprint(source)
    prompt = read_prompt(terms_file)
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    input_meta_file = output_dir / "jiangdao_asr_input.json"
    result_file = output_dir / "asr_result.json"
    expected = {
        "source": str(source),
        "fingerprint": source_fingerprint,
        "engine": "mlx-whisper",
        "model": model_ref,
        "prompt_sha256": prompt_hash,
    }
    if result_file.exists() and result_file.stat().st_size > 0 and input_meta_file.exists():
        try:
            current = json.loads(input_meta_file.read_text(encoding="utf-8"))
            if all(current.get(key) == value for key, value in expected.items()):
                current["cache_hit"] = True
                current["last_used_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                input_meta_file.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({"cache_hit": True, "result": str(result_file)}, ensure_ascii=False))
                return
        except (OSError, json.JSONDecodeError):
            pass

    started = time.time()
    raw = mlx_whisper.transcribe(
        str(source),
        path_or_hf_repo=model_ref,
        language=os.environ.get("JIANGDAO_ASR_LANGUAGE", "zh"),
        task="transcribe",
        condition_on_previous_text=False,
        word_timestamps=True,
        hallucination_silence_threshold=2.0,
        initial_prompt=prompt,
        verbose=False,
    )
    normalized, filtered = normalize_result(raw, duration)
    if not normalized["utterances"]:
        raise RuntimeError("本地识别没有得到有效语音段")

    (output_dir / "mlx_whisper_raw.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    write_text_outputs(output_dir, normalized["utterances"])
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    input_meta_file.write_text(
        json.dumps(
            {
                **expected,
                "duration_seconds": duration,
                "terms_file": str(Path(terms_file).resolve()) if terms_file else None,
                "cache_hit": False,
                "generated_at": generated_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "local_asr_meta.json").write_text(
        json.dumps(
            {
                "provider": "local",
                "engine": "mlx-whisper",
                "model": model_ref,
                "language": normalized.get("language"),
                "elapsed_seconds": round(time.time() - started, 3),
                "media_duration_seconds": duration,
                "utterances": len(normalized["utterances"]),
                "characters": sum(len(item["text"]) for item in normalized["utterances"]),
                "filtered_segments": filtered,
                "speaker_diarization": "not_run",
                "generated_at": generated_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "cache_hit": False,
                "utterances": len(normalized["utterances"]),
                "characters": sum(len(item["text"]) for item in normalized["utterances"]),
                "result": str(result_file),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
