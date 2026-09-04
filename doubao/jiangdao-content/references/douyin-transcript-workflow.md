# 抖音采集与内容证据验收流程

本合同由内容编导分身持有。凡任务包含抖音搜索、爆款采集、链接拆解或批量研究，逐条执行本流程。目标是取得可追溯的媒体、数据、评论和完整内容证据，并阻止“视频已下载”被汇报成“样本已完成”。

## 1. 状态分层

每条样本分别记录以下状态，不用一个“成功”覆盖整条链路：

- 任务状态：`running / partial / completed / failed`；
- 工件状态：媒体、元数据、评论、ASR、逐字稿、语义复核、视觉复核分别记录 `passed / pending / failed / not_required`；
- 样本状态：
  - `candidate`：已取得部分证据，仍有必要工件或复核未完成；
  - `content_ready`：已经能够可靠理解完整内容；
  - `market_ready`：`content_ready`，且点赞门槛、有效评论与评论复核全部通过；
  - `index_only`：只有标题、首屏、摘要、评论或其他索引证据；
  - `failed`：来源或关键工件明确失败，现有路线无法恢复。

正式市场样本沿用 `qualified=true` 兼容字段，其含义固定等于 `market_ready=true`。批量目标只统计 `qualified`。旧记录不会因规则更新自动改判；恢复旧任务时按本流程重新验收。

## 2. 独立目录与采集

为本轮创建独立临时目录，媒体、ASR 和验收中间文件留在临时目录；项目资料包归档来源、处理索引、内部逐字稿、评论、视觉证据和最终验收报告。

```bash
batch_tmp="/tmp/jiangdao-douyin-<任务ID>"
mkdir -p "$batch_tmp/media" "$batch_tmp/asr" "$batch_tmp/meta" "$batch_tmp/review"
```

正式下载器位置按 [运行配置合同](../../shared/runtime-configuration.md) 的 `douyin_downloader` 或环境变量读取；未配置时使用当前工作项目的 `tools/douyin-downloader`，当前锁定已验收提交 `203c1ae078bb3cc1d47f36672ac126e5cf80dee3`，版本和 Python 虚拟环境都保留在该目录。登录 Cookie 保存为下载器目录中权限为 `0600` 的 `.cookies.json`，不得复制进任务资料包、Skill 文档或运行报告。运行 `python <已安装内容编导目录>/scripts/check-skill-dependencies.py --stage douyin` 会同时检查安装目录、运行环境、许可证和版本。

取得标准链接后，为单条样本建立独立输出目录，运行正式采集入口：

```bash
python skills/jiangdao-content/scripts/collect-douyin.py \
  "$video_url" \
  "$batch_tmp/collector/$sample_id" \
  --report "$batch_tmp/meta/$sample_id-acquisition.json"
```

只有报告中的 `acquisition_state=completed` 才代表媒体、元数据和评论响应均已真实落盘。`partial` 或 `failed` 时按报告中的工件缺口处理。采集完成后的样本状态仍是 `candidate`，必须继续执行内容证据验收。

正式采集入口不可用时，媒体可以先走转写 Skill 的稳定脚本：

```bash
skills/jiangdao-transcribe/scripts/fetch-douyin-media.sh \
  "$video_url" \
  "$batch_tmp/media/$sample_id.mp4" \
  "$sec_uid" \
  > "$batch_tmp/meta/$sample_id-media.json"
```

作者作品列表找不到目标 ID 时，核对作品 ID 与作者链接、刷新一次媒体地址，再转入 MediaCrawler。登录、验证码或设备确认需要真人处理，状态写 `partial` 或 `AUTH_REQUIRED`，不循环撞风控。正式下载器 Cookie 失效时，在其目录运行 `.venv/bin/python -m tools.cookie_fetcher --config config.yml`，由用户完成登录。

下载器只负责媒体、元数据、评论和失败记录。下载器显示成功时，任务最多到“采集层完成”；后续内容证据验收仍需独立执行。

## 3. 先判断内容证据类型

媒体取得后先填写 `evidence_mode`，不得留空：

| 类型 | 适用内容 | 正式内容证据 |
|---|---|---|
| `speech_primary` | 单人口播、访谈讲述、画面只作陪衬 | 完整逐字稿＋语义复核 |
| `hybrid` | 剧情、现场互动、动画讲解、字幕或画面参与理解 | 完整逐字稿＋语义复核＋视觉证据 |
| `visual_primary` | 画图猜题、无有效口播、主要信息在图片或画面 | 完整 OCR、逐镜记录或能还原全文的视觉证据；ASR 标 `not_required` |

无法确认类型时停在 `candidate`。纯画面内容出现异常 ASR 时保留失败记录，不把该文本当正文；改走 OCR、逐镜记录或人工画面复核。

## 4. 语音内容的转写与自动检查

`speech_primary` 和 `hybrid` 在 MP4 验收后运行本机 ASR：

```bash
skills/jiangdao-transcribe/scripts/run-local-asr.sh \
  "$batch_tmp/media/$sample_id.mp4" \
  "$batch_tmp/asr/$sample_id"
```

生成内部研究逐字稿后立即执行：

```bash
skills/jiangdao-content/scripts/check-douyin-transcript.js \
  "$batch_tmp/media/$sample_id.mp4" \
  "$batch_tmp/asr/$sample_id/asr_result.json" \
  "$task_package/逐字稿/$sample_id.md"
```

自动检查覆盖：媒体与时长、ASR 段数、首尾覆盖、正文长度、重复词、重复行、字符与 n-gram 多样性、异常文字体系、文字密度。`Button` 连续重复、短视频生成不可能数量的文字、外文字符循环等情况直接失败。

自动检查通过后仍要做语义复核，确认文本能可靠还原视频在讲什么。大量同音错字、诗词/专名严重误识别、问答关系错乱或读完无法理解时，`semantic_review.status` 写 `failed` 或 `pending`，样本不得进入正式拆解。

## 5. 视觉与评论复核

- `hybrid` 和 `visual_primary` 必须保存原媒体、带时间点的截图/联系表、完整 OCR 或逐镜记录；`visual_review.status=passed` 时至少有一个真实存在的证据文件。
- 评论文件存在只说明抓取成功。还要筛除纯表情、无意义夸赞、重复内容和营销灌水，确认达到当前有效评论门槛，再把 `comments_review.status` 写为 `passed`。
- 评论、语义或视觉状态为 `pending` 时，整条任务状态只能是 `partial`。

## 6. 整条样本验收

为每条样本准备 JSON 清单：

```json
{
  "sample_id": "DY-123",
  "media_file": "media/DY-123.mp4",
  "metadata_file": "meta/DY-123-data.json",
  "comments_file": "meta/DY-123-comments.json",
  "asr_file": "asr/DY-123/asr_result.json",
  "transcript_file": "逐字稿/DY-123.md",
  "evidence_mode": "hybrid",
  "semantic_review": {"status": "passed", "note": "文本可理解，专名已核对"},
  "visual_review": {
    "status": "passed",
    "evidence_files": ["review/DY-123-contact.jpg"],
    "note": "已核验关键时间点"
  },
  "comments_review": {"status": "passed", "note": "保留5条有效评论"},
  "minimum_likes": 1000,
  "minimum_effective_comments": 3
}
```

相对路径以清单文件所在目录为基准。执行整条验收：

```bash
python skills/jiangdao-content/scripts/check-douyin-sample.py \
  "$batch_tmp/meta/$sample_id-acceptance.json" \
  --output "$batch_tmp/meta/$sample_id-acceptance-report.json"
```

只有报告同时满足 `job_status=completed`、`sample_state=market_ready`、`qualified=true`，才计入正式样本。`content_ready` 可以服务单条内容研究，但点赞或评论缺口仍会阻止它支撑赛道规律和市场验证。

## 7. 批量循环与汇报

```text
取候选 → 查重 → 获取媒体/数据/评论 → 判断证据类型
  → ASR 或视觉取证 → 自动检查 → 语义/视觉/评论复核 → 整条验收
  ├─ qualified=true：合格数 +1，进入正式拆解
  ├─ content_ready：保留为内容材料，披露市场证据缺口
  ├─ candidate / index_only：记录缺口并继续递补
  └─ failed：记录失败层级并继续递补
```

批量任务只有合格数达到目标，才能写 `completed`。候选耗尽时写 `partial`，同时报告候选数、`qualified/目标数`、`content_ready` 数、`index_only` 数、失败数和每条缺口。正式拆解卡数、后台《爆款借鉴索引》样本数和 `qualified` 数必须一致。

## 8. 禁止假完成

- 不把登录完成、接口返回、视频下载或 ASR 运行写成整条采集完成；
- 不把自动检查通过写成语义可用；
- 不用标题、首屏、章节摘要、评论或乱码逐字稿替代完整内容；
- 不在语义、视觉或评论复核缺失时生成完整内容级拆解；
- 不把纯画面内容的异常 ASR 写入详情页；
- 不因单个签名地址失效就认定平台没有媒体。
