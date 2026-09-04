#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const contract = path.join(root, 'shared/content-frontstage-format-contract.md');
const callers = [
  'jiangdao-content/SKILL.md',
  'jiangdao-deconstruct/SKILL.md',
  'jiangdao-adapt-topic/SKILL.md',
  'jiangdao-produce/SKILL.md',
  'jiangdao-transcribe/SKILL.md',
  'jiangdao-review/SKILL.md',
  'jiangdao-edit/SKILL.md',
  'jiangdao-publish/SKILL.md',
];

const requiredContractText = [
  '# 内容种子候选清单',
  '还需要你补充什么：',
  '内容概览：',
  '内容推进：',
  '### 01 来源与数据',
  '### 02 推送语与推送标签',
  '### 03 完整逐字稿',
  '### 04 赛道问题',
  '### 05 选题怎么来的',
  '### 06 原选题',
  '### 07 作者答案',
  '作者怎样讲清楚：',
  '### 08 为什么能传播',
  '### 09 评论区洞察',
  '### 10 最值得拿走',
  '主要带走：',
  '具体借法：',
  '下一步用途：',
  '# 选题候选清单',
  '题源范围：单篇题源共创｜围绕这一篇拆出的赛道问题继续加工，不代表赛道已经验证。',
  '## 1｜<一句自然、直接的完整选题；开放问题或待认领的方向性命题>',
  '<重复相同单条结构，连续编号至 10>',
  '# 生产决策卡',
  '# 可拍摄逐字稿',
  '# 发布复盘卡',
];

const failures = [];
const contractText = fs.readFileSync(contract, 'utf8');

let previousIndex = -1;
for (const text of requiredContractText) {
  const currentIndex = contractText.indexOf(text);
  if (currentIndex === -1) {
    failures.push(`合同缺少固定文本: ${text}`);
    continue;
  }
  if (currentIndex <= previousIndex) failures.push(`合同固定栏目顺序错误: ${text}`);
  previousIndex = currentIndex;
}

for (const relative of callers) {
  const file = path.join(root, relative);
  const text = fs.readFileSync(file, 'utf8');
  if (!text.includes('content-frontstage-format-contract.md')) {
    failures.push(`未引用前台格式合同: ${relative}`);
  }
}

const productionSkillText = fs.readFileSync(path.join(root, 'jiangdao-produce/SKILL.md'), 'utf8');
for (const text of ['production-input-gate.md', 'validate-production-input.py', 'PRODUCTION_INPUT_OK']) {
  if (!productionSkillText.includes(text)) failures.push(`内容生产入口缺少单条资料门: ${text}`);
}

const contentEntryText = fs.readFileSync(path.join(root, 'jiangdao-content/SKILL.md'), 'utf8');
const contentEntryLines = contentEntryText.split(/\r?\n/).length;
if (contentEntryLines > 130) failures.push(`内容编导总入口重新变得过重: ${contentEntryLines} lines`);
for (const heading of ['## 赛道关键词启动接口', '## 抖音逐字稿硬闸门', '## 不可混淆的总原则', '## 回复底部：下一步动作指引']) {
  if (contentEntryText.includes(heading)) failures.push(`内容编导总入口重复实现细则: ${heading}`);
}

for (const text of [
  '正式交付物',
  '普通交流',
  '使用自然语言，不套模板',
  '不强行追加《下一步》',
]) {
  if (!contractText.includes(text)) failures.push(`前台合同缺少自然表达规则: ${text}`);
}

const trackDatabaseTemplate = path.join(root, 'jiangdao-content/references/track-database-template.md');
const trackDatabaseText = fs.readFileSync(trackDatabaseTemplate, 'utf8');
const requiredTrackModules = [
  '## 01 赛道理解',
  '## 02 赛道问题池',
  '## 03 用户语言与评论问题库',
  '## 04 赛道传播规律',
];

let previousTrackModuleIndex = -1;
for (const text of requiredTrackModules) {
  const currentIndex = trackDatabaseText.indexOf(text);
  if (currentIndex === -1) {
    failures.push(`赛道数据库规格缺少模块: ${text}`);
    continue;
  }
  if (currentIndex <= previousTrackModuleIndex) failures.push(`赛道数据库模块顺序错误: ${text}`);
  previousTrackModuleIndex = currentIndex;
}

for (const text of [
  '## 选题共创怎样读取数据库',
  '具体选题和短期内容机会在选题共创阶段生成',
  'track-database-compilation-contract.md',
  'compile-track-database.mjs',
  'validate-track-database-v2.mjs',
]) {
  if (!trackDatabaseText.includes(text)) failures.push(`赛道数据库规格缺少治理规则: ${text}`);
}

if (!contractText.includes('track-database-template.md')) {
  failures.push('前台格式合同未指向赛道数据库结构真源');
}

const migrationScript = fs.readFileSync(path.join(root, 'jiangdao-content/scripts/migrate-track-database-v1.js'), 'utf8');
for (const key of [
  'track_understanding',
  'track_problem_pool',
  'topic_archetype_library',
  'user_language_and_comment_question_library',
  'track_spread_patterns',
  'aggregation_gaps',
]) {
  if (!migrationScript.includes(key)) failures.push(`赛道数据库迁移脚本缺少字段: ${key}`);
}

for (const text of ['赛道汇总迁移候选.md', '不会覆盖正式《赛道与内容数据库》入口']) {
  if (!migrationScript.includes(text)) failures.push(`赛道数据库迁移脚本缺少安全边界: ${text}`);
}

const forbiddenFiles = [
  'jiangdao-content/SKILL.md',
  'jiangdao-deconstruct/SKILL.md',
  'jiangdao-adapt-topic/SKILL.md',
];

for (const relative of forbiddenFiles) {
  const file = path.join(root, relative);
  const text = fs.readFileSync(file, 'utf8');
  for (const word of ['原作肉身', '肉身保留']) {
    if (text.includes(word)) failures.push(`发现废弃前台术语 ${word}: ${relative}`);
  }
}

const staleFormatChecks = [
  ['shared/content-framework-contract.md', '用户前台只展示三项'],
  ['jiangdao-content/references/orchestration-contract.md', '基础问题、原选题、作者答案、标题钩子、四段传播链'],
  ['jiangdao-deconstruct/references/sample-card-contract.md', '1. 来源、作者、标题、数据、原链接和逐字稿入口'],
  ['jiangdao-adapt-topic/SKILL.md', '固定展示 5 条'],
  ['jiangdao-adapt-topic/references/topic-candidate-contract.md', '候选数量固定为 5'],
  ['shared/content-frontstage-format-contract.md', ['## 市场痛点型｜', '4条'].join('')],
  ['shared/content-frontstage-format-contract.md', ['## 高感知收益型｜', '3条'].join('')],
  ['shared/content-frontstage-format-contract.md', ['## 本我内容种子型｜', '3条'].join('')],
  ['jiangdao-adapt-topic/SKILL.md', ['三类', '配比'].join('')],
  ['shared/content-frontstage-format-contract.md', ['### 原作', '还原层'].join('')],
  ['shared/content-frontstage-format-contract.md', ['### 分析', '判断层'].join('')],
  ['jiangdao-deconstruct/SKILL.md', ['每篇只展示“原作', '还原层”和“分析判断层”'].join('')],
  ['jiangdao-content/references/orchestration-contract.md', ['两层《逐篇', '爆款拆解》'].join('')],
  ['jiangdao-content/references/track-database-detail-page.md', ['评论区分析放在', '爆款拆解之前'].join('')],
  ['jiangdao-deconstruct/agents/openai.yaml', '爆款借鉴决策表'],
  ['jiangdao-deconstruct/references/sample-card-contract.md', '### 01《赛道问题池》'],
  ['jiangdao-content/references/orchestration-contract.md', '- **赛道问题池**：'],
  ['jiangdao-deconstruct/SKILL.md', '每篇依次展示 01 来源与数据'],
  ['jiangdao-adapt-topic/references/topic-candidate-contract.md', '1. 先读“当前内容机会”和“高价值选题池”'],
  ['jiangdao-content/references/orchestration-contract.md', '单条内容不构成内容编导从 0→1 生成新选题和新逐字稿的足量语料'],
  ['jiangdao-produce/references/production-workflows.md', '不能单独支撑内容编导生成新的选题和逐字稿'],
  ['jiangdao-adapt-topic/references/topic-candidate-contract.md', 'topic-candidate-audit-v1'],
  ['jiangdao-produce/SKILL.md', '达到 `jiangdao-content` 当前采集目标的合格爆款文本库'],
  ['jiangdao-produce/references/production-workflows.md', '内容生产默认读取达到 `jiangdao-content` 当前采集目标的合格爆款文本库'],
  ['jiangdao-produce/references/production-workflows.md', '内容生产默认基于达到当前目标的合格爆款文本库'],
  ['jiangdao-content/SKILL.md', '其他任务先核对合格爆款文本库是否达到当前目标'],
  ['shared/content-frontstage-format-contract.md', '内容编导前台回复最底部固定为'],
  ['jiangdao-content/SKILL.md', '每次前台回复都必须在最底部使用'],
];

for (const [relative, stale] of staleFormatChecks) {
  const file = path.join(root, relative);
  const text = fs.readFileSync(file, 'utf8');
  if (text.includes(stale)) failures.push(`发现旧版格式定义: ${relative} -> ${stale}`);
}

if (failures.length) {
  process.stderr.write(`${failures.join('\n')}\n`);
  process.exit(1);
}

process.stdout.write(`format_contract_ok=true callers=${callers.length}\n`);
