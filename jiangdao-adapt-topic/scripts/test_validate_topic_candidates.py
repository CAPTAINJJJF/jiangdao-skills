#!/usr/bin/env python3
"""Forward tests for topic-candidate quality validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


VALIDATOR = Path(__file__).with_name("validate-topic-candidates.py")


class TopicCandidateValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.pool_path = self.root / "赛道汇总库.json"
        self.task_path = self.root / "当前内容任务.md"
        self.candidate_path = self.root / "选题候选清单.md"
        self.audit_path = self.root / "选题候选审计.json"

        self.problem_one = "个人创作者怎样持续更新，同时让内容保持真实和共鸣？"
        self.problem_two = "AI参与内容生产后，人应该保留哪些判断？"
        self.pool_path.write_text(
            json.dumps(
                {
                    "track_problem_pool": [
                        {"problem_id": "P001", "problem": self.problem_one, "sources": ["S001"]},
                        {"problem_id": "P002", "problem": self.problem_two, "sources": ["S002"]},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.task_path.write_text(
            "目标人群：没有团队的个人创作者\n本轮只研究持续更新与真实表达。\n",
            encoding="utf-8",
        )
        source_link = f"[正式问题池]({self.pool_path})"
        self.topic_one = "没有团队的个人创作者，怎样持续更新又保留真实表达？"
        self.candidate_path.write_text(
            "\n".join(
                [
                    "# 选题候选清单", "",
                    f"## 1｜{self.topic_one}",
                    f"题源原话：{self.problem_one}",
                    "生成关系：保留持续更新与真实表达的核心需求，使用选题具体化，增加没有团队的个人创作者这一限制条件。",
                    "建议：可以考虑讨论制作负担、反馈周期和表达失真之间的关系。",
                    f"来源：{source_link}", "",
                    f"## 2｜{self.problem_two}",
                    f"题源原话：{self.problem_two}",
                    "生成关系：保留AI参与内容生产后人的判断权这一核心需求，本题未加工，直接保留原问题。",
                    "建议：可以考虑区分标准动作、关键判断和最终验收。",
                    f"来源：{source_link}", "",
                ]
            ),
            encoding="utf-8",
        )
        self.audit = {
            "schema_version": "topic-candidate-audit-v3",
            "topic_mode": "track_pool",
            "calibration_state": "ready",
            "calibration_basis": {
                "confirmed_by_user": True,
                "target_audience": "没有团队的个人创作者",
                "confirmed_rules": ["题面要让目标客户感知真实损益"],
                "positive_examples": ["没有团队时，持续更新最容易牺牲什么？"],
                "negative_examples": ["普通换词没有长出新的讨论空间"],
            },
            "allowed_source_problem_ids": ["P001", "P002"],
            "problem_pool_file": str(self.pool_path),
            "current_task_file": str(self.task_path),
            "candidates": [
                {
                    "number": 1,
                    "topic": self.topic_one,
                    "source_problem_id": "P001",
                    "source_problem": self.problem_one,
                    "core_need": "持续更新与真实表达",
                    "processing_actions": ["选题具体化"],
                    "development_path": "现场处理",
                    "topic_form": "open_question",
                    "added_elements": [
                        {
                            "type": "限制条件",
                            "value": "没有团队的个人创作者",
                            "basis_source": str(self.task_path),
                            "basis_quote": "没有团队的个人创作者",
                        }
                    ],
                    "difference": "把宽泛创作者问题收窄到没有团队的个人创作者",
                    "target_stakes": "持续更新时可能牺牲真实表达和用户共鸣",
                    "target_click_reason": "没有团队的创作者会直接代入自己的更新压力",
                    "content_capacity": "可以展开制作负担、反馈周期、表达失真和调整方法",
                    "resonance_scope": "覆盖缺少团队支持的个人创作者这一明确目标人群",
                    "wrong_audience_risk": "题目直接服务个人创作者，没有明显错受众风险",
                    "verdicts": self.passed_verdicts(),
                    "reasons": {
                        "semantic_relation": "题源与新题都讨论持续更新和真实表达",
                        "grounding": "限制条件来自当前内容任务原话",
                        "stakes": "持续更新可能以表达失真为代价",
                        "audience": "目标人群会把制作压力代入自身",
                        "capacity": "可以展开多个原因、判断和处理动作",
                        "novelty": "新增没有团队这一真实决策环境",
                        "deliverability": "可以解释制作负担与表达保持的方法",
                        "identity": "题面使用目标人群，不借用第三方成绩",
                    },
                },
                {
                    "number": 2,
                    "topic": self.problem_two,
                    "source_problem_id": "P002",
                    "source_problem": self.problem_two,
                    "core_need": "AI参与内容生产后人的判断",
                    "processing_actions": ["未加工"],
                    "development_path": "用户校准路径",
                    "topic_form": "open_question",
                    "added_elements": [],
                    "difference": "原问题已经具体且答案开放，保持原题",
                    "target_stakes": "错误交出关键判断会让内容失去人的责任和取舍",
                    "target_click_reason": "使用AI做内容的人需要判断哪些环节不能交出去",
                    "content_capacity": "可以展开标准动作、关键判断、最终验收和责任边界",
                    "resonance_scope": "覆盖正在使用AI参与内容生产的目标创作者",
                    "wrong_audience_risk": "题目服务AI内容创作者，没有明显错受众风险",
                    "verdicts": self.passed_verdicts(),
                    "reasons": {
                        "semantic_relation": "题源与候选完全一致",
                        "grounding": "没有增加新的题面元素",
                        "stakes": "失去人的判断会影响内容责任和质量",
                        "audience": "使用AI的创作者会直接关心判断边界",
                        "capacity": "可以展开多个工作环节和判断类型",
                        "novelty": "题源本身已经是完整选题，因此保留原题",
                        "deliverability": "可以区分不同类型的人类判断",
                        "identity": "题面没有身份成绩迁移",
                    },
                },
            ],
        }
        self.write_audit(self.audit)

    @staticmethod
    def passed_verdicts() -> dict[str, bool]:
        return {
            "core_need_preserved": True,
            "added_elements_grounded": True,
            "substantial_processing": True,
            "target_audience_fit": True,
            "stakes_visible": True,
            "whole_topic": True,
            "resonance_sufficient": True,
            "expression_space_preserved": True,
            "deliverable": True,
            "task_fit": True,
            "identity_safe": True,
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_audit(self, value: dict) -> None:
        self.audit_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def run_validator(self, mode: str = "track_pool") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(VALIDATOR), str(self.candidate_path),
                "--audit", str(self.audit_path),
                "--problem-pool", str(self.pool_path),
                "--mode", mode,
                "--count", "2",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_candidates_pass(self) -> None:
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VALIDATION_OK 2/2", result.stdout)
        self.assertIn("mode=track_pool", result.stdout)

    def test_single_source_candidates_pass_with_scope_notice(self) -> None:
        source_link = f"[正式问题池]({self.pool_path})"
        self.candidate_path.write_text(
            "\n".join(
                [
                    "# 选题候选清单", "",
                    "题源范围：单篇题源共创｜围绕这一篇拆出的赛道问题继续加工，不代表赛道已经验证。", "",
                    f"## 1｜{self.topic_one}",
                    f"题源原话：{self.problem_one}",
                    "生成关系：保留持续更新与真实表达的核心需求，使用选题具体化，增加没有团队的个人创作者这一限制条件。",
                    "建议：可以考虑讨论制作负担、反馈周期和表达失真之间的关系。",
                    f"来源：{source_link}", "",
                    f"## 2｜{self.problem_one}",
                    f"题源原话：{self.problem_one}",
                    "生成关系：保留持续更新与真实表达的核心需求，本题未加工，直接保留原问题。",
                    "建议：可以考虑区分更新频率、真实材料和用户共鸣之间的关系。",
                    f"来源：{source_link}", "",
                ]
            ),
            encoding="utf-8",
        )
        audit = copy.deepcopy(self.audit)
        audit["topic_mode"] = "single_source"
        audit["allowed_source_problem_ids"] = ["P001"]
        audit["single_source_record_id"] = "S001"
        audit["candidates"][1] = {
            "number": 2,
            "topic": self.problem_one,
            "source_problem_id": "P001",
            "source_problem": self.problem_one,
            "core_need": "持续更新与真实表达",
            "processing_actions": ["未加工"],
            "development_path": "用户校准路径",
            "topic_form": "open_question",
            "added_elements": [],
            "difference": "原问题已经能够独立形成讨论，保持题源原话",
            "target_stakes": "持续更新时可能牺牲真实表达和用户共鸣",
            "target_click_reason": "个人创作者需要解决更新与真实表达的冲突",
            "content_capacity": "可以展开更新频率、真实材料、用户反馈和调整方法",
            "resonance_scope": "覆盖需要长期更新的个人创作者",
            "wrong_audience_risk": "题目直接服务个人创作者，没有明显错受众风险",
            "verdicts": self.passed_verdicts(),
            "reasons": {
                "semantic_relation": "候选完整保留题源问题",
                "grounding": "没有增加题源以外的新元素",
                "stakes": "持续更新可能损失表达真实感",
                "audience": "个人创作者会直接关心持续更新",
                "capacity": "可以展开多个原因、判断和处理动作",
                "novelty": "题源本身已经能够形成完整内容",
                "deliverability": "可以讨论更新与真实表达的平衡",
                "identity": "题面没有迁移第三方身份成绩",
            },
        }
        self.write_audit(audit)
        result = self.run_validator("single_source")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mode=single_source", result.stdout)

    def test_mode_mismatch_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["topic_mode"] = "single_source"
        audit["allowed_source_problem_ids"] = ["P001"]
        audit["single_source_record_id"] = "S001"
        self.write_audit(audit)
        result = self.run_validator("track_pool")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TOPIC_MODE_MISMATCH", result.stdout)

    def test_track_pool_scope_too_narrow_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["allowed_source_problem_ids"] = ["P001"]
        self.write_audit(audit)
        result = self.run_validator("track_pool")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TRACK_POOL_SCOPE_INSUFFICIENT", result.stdout)

    def test_unknown_source_problem_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["source_problem_id"] = "P999"
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SOURCE_PROBLEM_NOT_IN_POOL", result.stdout)

    def test_ungrounded_added_element_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["added_elements"][0]["basis_quote"] = "每天只有一小时"
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ADDED_ELEMENT_UNGROUNDED", result.stdout)

    def test_answer_leak_fails(self) -> None:
        leaked = "个人创作者持续更新的关键在于降低制作负担？"
        text = self.candidate_path.read_text(encoding="utf-8").replace(self.topic_one, leaked, 1)
        self.candidate_path.write_text(text, encoding="utf-8")
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["topic"] = leaked
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ANSWER_LEAK_IN_TOPIC", result.stdout)

    def test_directional_hypothesis_passes_without_question_mark(self) -> None:
        directional = "没有团队的个人创作者，持续更新最容易先丢掉真实表达"
        text = self.candidate_path.read_text(encoding="utf-8").replace(self.topic_one, directional, 1)
        self.candidate_path.write_text(text, encoding="utf-8")
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["topic"] = directional
        audit["candidates"][0]["topic_form"] = "directional_hypothesis"
        self.write_audit(audit)
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_user_calibration_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["calibration_state"] = "needs_calibration"
        audit["calibration_basis"]["confirmed_by_user"] = False
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CALIBRATION_NOT_READY", result.stdout)
        self.assertIn("CALIBRATION_NOT_USER_CONFIRMED", result.stdout)

    def test_wrong_audience_risk_gate_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["verdicts"]["target_audience_fit"] = False
        audit["candidates"][0]["wrong_audience_risk"] = "主要吸引员工批评领导，目标管理者会避开"
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VERDICT_NOT_PASSED", result.stdout)
        self.assertIn("target_audience_fit", result.stdout)

    def test_signal_too_small_for_whole_topic_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["verdicts"]["whole_topic"] = False
        audit["candidates"][0]["content_capacity"] = "只能作为正文里的一个异常信号"
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VERDICT_NOT_PASSED", result.stdout)
        self.assertIn("whole_topic", result.stdout)

    def test_source_paraphrase_fails_when_claimed_as_processing(self) -> None:
        paraphrase = "个人创作者怎样持续更新，同时让内容保持真实和共鸣呢？"
        text = self.candidate_path.read_text(encoding="utf-8").replace(self.topic_one, paraphrase, 1)
        self.candidate_path.write_text(text, encoding="utf-8")
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["topic"] = paraphrase
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SOURCE_NEAR_PARAPHRASE", result.stdout)

    def test_added_element_already_in_source_fails(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["candidates"][0]["added_elements"][0] = {
            "type": "限制条件",
            "value": "个人创作者",
            "basis_source": str(self.task_path),
            "basis_quote": "个人创作者",
        }
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ADDED_ELEMENT_ALREADY_IN_SOURCE", result.stdout)

    def test_near_duplicate_fails(self) -> None:
        duplicate = "没有团队的个人创作者，怎样持续更新并保留真实表达？"
        text = self.candidate_path.read_text(encoding="utf-8").replace(
            f"## 2｜{self.problem_two}", f"## 2｜{duplicate}"
        )
        self.candidate_path.write_text(text, encoding="utf-8")
        audit = copy.deepcopy(self.audit)
        audit["candidates"][1]["topic"] = duplicate
        self.write_audit(audit)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TOPIC_NEAR_DUPLICATE", result.stdout)


if __name__ == "__main__":
    unittest.main()
