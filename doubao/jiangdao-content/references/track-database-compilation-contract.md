# 赛道数据库通用编译合同

本合同负责把当前版本单条拆解增量，稳定装配为任意 IP、学员或多赛道项目可用的《赛道数据库》。编译程序不写行业结论；内容编导先完成语义归并和自然表达，再由程序核验证据与装配结果。

## 输入链

固定分成两层：

1. **单条证据层**：来源记录、赛道问题、作者答案、真实评论、原作选题加工和单条传播信号；
2. **跨样本聚合层**：赛道理解、问题归并、用户回应地图、传播规律和后台选题加工库。

两层统一保存为一份 `赛道数据库编译资料包.json`。资料包不得直接复制其他 IP 的赛道名、核心词、行业结论或内容机会。

## 资料包结构

```json
{
  "schema_version": "track-database-compilation-v1",
  "evidence_root": ".",
  "core_track_keywords": ["已确认核心赛道词"],
  "source_records": [
    {
      "record_id": "S001",
      "title": "来源内容标题",
      "detail_path": "详情/S001.md",
      "input_state": "full_text"
    }
  ],
  "source_problems": [
    {
      "source_problem_id": "SP001",
      "question": "单条拆解卡中的完整赛道问题？",
      "record_id": "S001",
      "track_ids": ["track-a"],
      "evidence_identity": "作者全文还原"
    }
  ],
  "answer_assets": [
    {
      "answer_id": "AN001",
      "record_id": "S001",
      "track_ids": ["track-a"],
      "text": "作者实际给出的答案摘要"
    }
  ],
  "comment_quotes": [
    {
      "quote_id": "Q001",
      "record_id": "S001",
      "track_ids": ["track-a"],
      "quote": "真实评论原话",
      "response_type": "用户继续追问什么",
      "evidence_path": "证据/S001-评论.md",
      "evidence_status": "real_user_quote"
    },
    {
      "quote_id": "Q002",
      "record_id": "S001",
      "track_ids": ["track-a"],
      "quote": "真实追问原话",
      "response_type": "用户会继续追问什么",
      "evidence_path": "证据/S001-评论.md",
      "evidence_status": "real_user_quote"
    },
    {
      "quote_id": "Q003",
      "record_id": "S001",
      "track_ids": ["track-a"],
      "quote": "真实反对原话",
      "response_type": "用户会质疑或反对什么",
      "evidence_path": "证据/S001-评论.md",
      "evidence_status": "real_user_quote"
    }
  ],
  "topic_processing_actions": [
    {
      "action_id": "A001",
      "record_id": "S001",
      "track_ids": ["track-a"],
      "action": "选题具体化",
      "evidence_quote": "拆解卡中对应的直接依据"
    }
  ],
  "spread_signals": [
    {
      "signal_id": "SS001",
      "record_id": "S001",
      "track_ids": ["track-a"],
      "text": "单条传播判断",
      "evidence_basis": "支持依据与边界"
    }
  ],
  "tracks": [
    {
      "track_id": "track-a",
      "display_name": "赛道名称",
      "role": "core",
      "confirmed_keyword": "已确认核心赛道词",
      "source_record_ids": ["S001"],
      "understanding": {
        "paragraphs": [
          {
            "text": "自然表达的一段赛道理解。",
            "aspects": ["industry_focus", "user_interest"],
            "evidence_ids": ["SP001", "Q001"]
          },
          {
            "text": "自然表达的一段变现与长期缺口判断。",
            "aspects": ["monetization", "long_term_gap"],
            "evidence_ids": ["AN001"]
          }
        ]
      },
      "problem_groups": [
        {
          "problem_id": "P001",
          "question": "跨样本归并后的完整问题句？",
          "source_problem_ids": ["SP001"],
          "merge_audit": {
            "shared_core_need": "共同保留的核心需求",
            "differences_change_answer": false,
            "reason": "为什么可以归到同一个问题"
          }
        }
      ],
      "excluded_source_problems": [],
      "user_response_map": {
        "status": "verified",
        "sections": [
          {
            "type": "用户容易认可什么",
            "insights": [{"text": "自然判断", "quote_ids": ["Q001"]}]
          },
          {
            "type": "用户会继续追问什么",
            "insights": [{"text": "自然判断", "quote_ids": ["Q002"]}]
          },
          {
            "type": "用户会质疑或反对什么",
            "insights": [{"text": "自然判断", "quote_ids": ["Q003"]}]
          },
          {
            "type": "这些反应说明什么",
            "insights": [{"text": "自然判断", "quote_ids": ["Q001", "Q002", "Q003"]}]
          }
        ]
      },
      "spread_patterns": [],
      "topic_processing_library": [
        {
          "library_id": "TA001",
          "action": "选题具体化",
          "source_action_ids": ["A001"],
          "applicable_condition": "什么情况下成立",
          "boundary": "什么情况下不能套用"
        }
      ],
      "aggregation_gaps": {"spread_patterns": "当前只有一个样本，暂不形成赛道传播规律"}
    }
  ]
}
```

`role` 只允许：

- `core`：当前 IP 持续经营的赛道；
- `business_contact`：工作中接触的用户行业。

业务接触赛道不得进入 `core_track_keywords`，也不得自动成为当前 IP 的选题来源。

评论不可得时，`user_response_map` 使用：

```json
{"status": "unavailable", "reason": "当前样本没有取得真实评论", "sections": []}
```

此时前台只显示证据缺口，不归纳认可、追问和反对。

## 跨样本归并要求

- 每个单条赛道问题，在所属赛道内必须进入一个问题组，或写入 `excluded_source_problems` 并说明理由；不能静默遗漏。
- 同一单条问题不能同时进入两个问题组。
- 合并问题必须保存共同核心需求、答案边界判断和合并理由；对象、阶段、场景或后果会改变答案时分开保留。
- 用户回应判断只能引用 `real_user_quote`；作者正文、剧情对白和 AI 推演不能进入评论证据。
- 正式传播规律至少连接两个独立来源记录和对应单条传播信号；单样本判断继续留在后台候选。
- 赛道理解的段落合计必须覆盖行业焦点、用户兴趣、变现方式和长期缺口，并能回链到本赛道证据。

## 编译与验收

先在新的空白暂存目录编译：

```bash
node scripts/compile-track-database.mjs \
  --manifest <赛道数据库编译资料包.json> \
  --out <空白暂存目录>
```

编译器固定生成：

```text
<暂存目录>/
├── 赛道数据库.md
└── 赛道数据库/
    ├── 赛道汇总库.json
    ├── 后台关联索引.json
    └── <赛道ID>/
        ├── 赛道数据库.md
        └── 赛道汇总库.json
```

随后运行：

```bash
node scripts/validate-track-database-v2.mjs \
  <暂存目录>/赛道数据库/赛道汇总库.json \
  <暂存目录>/赛道数据库.md
```

只有编译和独立校验都通过，才切换正式入口。编译器拒绝写入非空目录；迁移旧库时先保留快照，避免直接覆盖现有数据库。

## 前台结果

前台只展示：核心赛道词，以及每个赛道完整连续的四部分内容。问题 ID、来源 ID、合并审计、样本数量、证据状态、后台加工库和运行信息全部留在结构化数据库。
