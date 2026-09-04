#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("check-douyin-sample.py")
SPEC = importlib.util.spec_from_file_location("check_douyin_sample", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class SampleGateTest(unittest.TestCase):
    def make_files(self, root: Path) -> None:
        (root / "video.mp4").write_bytes(b"video")
        (root / "asr.json").write_text("{}", encoding="utf-8")
        (root / "transcript.md").write_text("## ASR 全文\n有效文本", encoding="utf-8")
        (root / "metadata.json").write_text(
            json.dumps(
                {
                    "aweme_id": "123",
                    "desc": "标题",
                    "author": {"nickname": "作者"},
                    "create_time": 1,
                    "statistics": {"digg_count": 1200},
                }
            ),
            encoding="utf-8",
        )
        (root / "comments.json").write_text(
            json.dumps({"comments": [{"text": "真实问题一"}, {"text": "真实问题二"}, {"text": "真实问题三"}]}),
            encoding="utf-8",
        )
        (root / "visual.jpg").write_bytes(b"visual")

    def write_manifest(self, root: Path, **overrides: object) -> Path:
        manifest = {
            "sample_id": "123",
            "media_file": "video.mp4",
            "metadata_file": "metadata.json",
            "comments_file": "comments.json",
            "asr_file": "asr.json",
            "transcript_file": "transcript.md",
            "evidence_mode": "hybrid",
            "semantic_review": {"status": "passed"},
            "visual_review": {"status": "passed", "evidence_files": ["visual.jpg"]},
            "comments_review": {"status": "passed"},
        }
        manifest.update(overrides)
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    @patch.object(gate, "probe_media", return_value={"status": "passed", "failures": []})
    @patch.object(gate, "run_transcript_checker", return_value={"qualified": True, "failures": []})
    def test_hybrid_sample_reaches_market_ready(self, _transcript: object, _media: object) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_files(root)
            report = gate.evaluate_manifest(self.write_manifest(root))
        self.assertTrue(report["qualified"])
        self.assertEqual(report["job_status"], "completed")
        self.assertEqual(report["sample_state"], "market_ready")

    @patch.object(gate, "probe_media", return_value={"status": "passed", "failures": []})
    @patch.object(gate, "run_transcript_checker", return_value={"qualified": True, "failures": []})
    def test_semantic_failure_stays_partial(self, _transcript: object, _media: object) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_files(root)
            path = self.write_manifest(root, semantic_review={"status": "failed"})
            report = gate.evaluate_manifest(path)
        self.assertFalse(report["qualified"])
        self.assertEqual(report["job_status"], "partial")
        self.assertIn("review:semantic_review_failed", report["blockers"])

    @patch.object(gate, "probe_media", return_value={"status": "passed", "failures": []})
    @patch.object(gate, "run_transcript_checker", return_value={"qualified": False, "failures": ["hallucination"]})
    def test_visual_primary_does_not_use_bad_asr(self, _transcript: object, _media: object) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_files(root)
            path = self.write_manifest(
                root,
                evidence_mode="visual_primary",
                semantic_review={"status": "not_applicable"},
            )
            report = gate.evaluate_manifest(path)
        self.assertTrue(report["qualified"])
        self.assertEqual(report["artifact_status"]["transcript"], "not_required")
        self.assertNotIn("transcript:hallucination", report["blockers"])

    @patch.object(gate, "probe_media", return_value={"status": "passed", "failures": []})
    @patch.object(gate, "run_transcript_checker", return_value={"qualified": True, "failures": []})
    def test_visual_pass_without_evidence_is_blocked(self, _transcript: object, _media: object) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_files(root)
            path = self.write_manifest(root, visual_review={"status": "passed"})
            report = gate.evaluate_manifest(path)
        self.assertFalse(report["qualified"])
        self.assertIn("review:visual_evidence_missing", report["blockers"])

    @patch.object(gate, "probe_media", return_value={"status": "passed", "failures": []})
    @patch.object(gate, "run_transcript_checker", return_value={"qualified": True, "failures": []})
    def test_comments_stay_pending_without_review(self, _transcript: object, _media: object) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_files(root)
            path = self.write_manifest(root, comments_review={"status": "pending"})
            report = gate.evaluate_manifest(path)
        self.assertFalse(report["qualified"])
        self.assertIn("review:comments_review_pending", report["blockers"])

    @patch.object(gate, "probe_media", return_value={"status": "passed", "failures": []})
    @patch.object(gate, "run_transcript_checker", return_value={"qualified": True, "failures": []})
    def test_unknown_evidence_mode_cannot_reach_content_ready(
        self,
        _transcript: object,
        _media: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_files(root)
            path = self.write_manifest(root, evidence_mode="unknown")
            report = gate.evaluate_manifest(path)
        self.assertFalse(report["content_ready"])
        self.assertIn("review:evidence_mode_unknown", report["blockers"])

    @patch.object(gate, "probe_media", return_value={"status": "passed", "failures": []})
    @patch.object(gate, "run_transcript_checker", return_value={"qualified": True, "failures": []})
    def test_missing_likes_can_be_content_ready_but_not_market_ready(
        self,
        _transcript: object,
        _media: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_files(root)
            metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            metadata["statistics"].pop("digg_count")
            (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            report = gate.evaluate_manifest(self.write_manifest(root))
        self.assertTrue(report["content_ready"])
        self.assertFalse(report["market_ready"])
        self.assertEqual(report["sample_state"], "content_ready")


if __name__ == "__main__":
    unittest.main()
