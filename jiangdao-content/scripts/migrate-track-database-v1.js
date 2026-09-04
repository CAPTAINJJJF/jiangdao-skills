#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

function arg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : null;
}

const projectRoot = arg('--project-root');
const batchDir = arg('--batch-dir');
const track = arg('--track');

if (!projectRoot || !batchDir || !track) {
  console.error('usage: migrate-track-database-v1.js --project-root <dir> --batch-dir <dir> --track <name>');
  process.exit(2);
}

const cardsDir = path.join(batchDir, '拆解卡');
const dbDir = path.join(projectRoot, '赛道数据库');
const detailsDir = path.join(dbDir, '爆款详情');
const xhsArchivePath = path.join(batchDir, '小红书原文与评论.md');
const xhsArchive = fs.existsSync(xhsArchivePath) ? fs.readFileSync(xhsArchivePath, 'utf8') : '';

fs.mkdirSync(detailsDir, { recursive: true });

function section(text, heading, nextHeading = null) {
  const start = text.indexOf(heading);
  if (start < 0) return '';
  const bodyStart = start + heading.length;
  let end = nextHeading ? text.indexOf(nextHeading, bodyStart) : -1;
  if (end < 0) {
    const match = text.slice(bodyStart).match(/\n## /);
    end = match ? bodyStart + match.index : text.length;
  }
  return text.slice(bodyStart, end).trim();
}

function firstSection(text, candidates) {
  for (const [heading, nextHeading] of candidates) {
    const body = section(text, heading, nextHeading);
    if (body) return body;
  }
  return '';
}

function xhsOriginal(id) {
  const marker = `## ${id}｜`;
  const start = xhsArchive.indexOf(marker);
  if (start < 0) return '';
  const next = xhsArchive.indexOf('\n## ', start + marker.length);
  return xhsArchive.slice(start, next < 0 ? xhsArchive.length : next).trim();
}

function field(text, label) {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = text.match(new RegExp(`^(?:- )?(?:\\*\\*)?${escaped}(?:\\*\\*)?：\\s*(.+)$`, 'm'));
  return match ? match[1].trim() : '';
}

function relativeFromDb(target) {
  return path.relative(dbDir, target).split(path.sep).join('/');
}

function relativeFromDetails(target) {
  return path.relative(detailsDir, target).split(path.sep).join('/');
}

function compactText(value, maxLength = 260) {
  const normalized = String(value || '').replace(/\s+/g, ' ').trim();
  return normalized.length > maxLength
    ? `${normalized.slice(0, maxLength)}…`
    : normalized;
}

const cardFiles = fs.readdirSync(cardsDir)
  .filter((name) => name.endsWith('.md'))
  .sort((a, b) => a.localeCompare(b, 'zh-CN', { numeric: true }));

const records = [];
const problems = [];
const topicArchetypeCandidates = [];
const spreadSignalCandidates = [];
const userLanguageCandidates = [];

function archetypeTypes(text) {
  const types = [];
  for (const type of ['元素迁移', '选题具体化', '收益显化', '损失显化']) {
    if (text.includes(type)) types.push(type);
  }
  return types.length ? types : ['待人工归类'];
}

function aggregateProblems(items) {
  const grouped = new Map();
  for (const item of items) {
    const key = item.text.replace(/\s+/g, ' ').trim();
    if (!grouped.has(key)) grouped.set(key, { ...item, sources: [], occurrence_count: 0 });
    const current = grouped.get(key);
    current.occurrence_count += 1;
    current.sources.push(...item.sources);
  }
  return [...grouped.values()].map((item, index) => ({
    problem_id: `PROBLEM-${String(index + 1).padStart(3, '0')}`,
    track_problem: item.text,
    target_group: '待从原卡复核',
    stage_and_scenario: '待从原卡复核',
    occurrence_count: item.occurrence_count,
    distinct_viral_count: new Set(item.sources).size,
    representative_virals: [...new Set(item.sources)],
    comment_derived_questions: [],
    evidence_state: item.evidence_state,
    sources: [...new Set(item.sources)],
    status: '迁移候选，待同义归并与用户证据复核'
  }));
}

for (const cardFile of cardFiles) {
  const cardPath = path.join(cardsDir, cardFile);
  const card = fs.readFileSync(cardPath, 'utf8');
  const id = (card.match(/^#\s+([^｜\s]+)/m) || [])[1];
  if (!id) continue;

  const source = firstSection(card, [
    ['## 01 来源与数据', '## 02 推送语与推送标签'],
    ['## 来源与证据', '## 原作内容'],
  ]);
  const sourceForDetail = source
    .split('\n')
    .filter((line) => !line.startsWith('- 完整内容：'))
    .join('\n');
  const sourceLine = source.split('\n').find((line) => line.startsWith('- ')) || '';
  const sourceParts = sourceLine.slice(2).split('｜');
  const platform = sourceParts[0] || '';
  const author = sourceParts.slice(1, -1).join('｜');
  const title = (sourceParts[sourceParts.length - 1] || id).replace(/^《|》$/g, '');
  const sourceUrl = (source.match(/https?:\/\/\S+/) || [''])[0];
  const inputState = field(source, '输入状态');
  const pushAndTags = section(card, '## 02 推送语与推送标签', '## 03 完整逐字稿');
  const trackProblemSection = section(card, '## 04 赛道问题', '## 05 选题怎么来的');
  const topicOrigin = section(card, '## 05 选题怎么来的', '## 06 原选题');
  const originalTopic = section(card, '## 06 原选题', '## 07 作者答案');
  const authorAnswer = section(card, '## 07 作者答案', '## 08 为什么能传播');
  const spreadReason = section(card, '## 08 为什么能传播', '## 09 评论区洞察');
  const commentInsight = firstSection(card, [
    ['## 09 评论区洞察', '## 10 最值得拿走'],
    ['## 评论区分析', '## 问题、选题、答案与表达'],
  ]);
  const takeaway = firstSection(card, [
    ['## 10 最值得拿走', null],
    ['## 评论与可挪用点', null],
  ]);

  const transcriptPath = path.join(batchDir, '逐字稿', `${id}.md`);
  const ocrPath = path.join(batchDir, '逐字稿', `${id}-逐页OCR.txt`);
  let originalText = '';
  let fullTextState = '';
  let sourceContentPath = '';
  let sourceOriginal = '';

  if (fs.existsSync(transcriptPath)) {
    originalText = fs.readFileSync(transcriptPath, 'utf8');
    fullTextState = '完整ASR逐字稿，待人工听校';
    sourceContentPath = transcriptPath;
  } else if (fs.existsSync(ocrPath)) {
    originalText = fs.readFileSync(ocrPath, 'utf8');
    fullTextState = '完整逐页机器OCR，待人工校对';
    sourceContentPath = ocrPath;
    sourceOriginal = xhsOriginal(id);
  } else {
    originalText = '[缺完整原文]';
    fullTextState = '缺完整原文';
  }

  let rawComments = `${commentInsight}\n${takeaway}\n${card}`
    .split('\n')
    .filter((line) => /评论原话|代表评论|有效评论|可见评论/.test(line))
    .join('\n');
  const archivedXhs = xhsOriginal(id);
  if (platform === '小红书' && archivedXhs) {
    const archivedCommentLines = archivedXhs.split('\n').filter((line) => /可见评论/.test(line));
    if (archivedCommentLines.length) rawComments = archivedCommentLines.join('\n');
  }
  if (!rawComments) rawComments = '当前归档没有可逐条展示的有效评论原文。';

  const pushCopy = field(pushAndTags, '推送语') || '不可得（当前归档未独立保存原始推送语）';
  const recommendationCopy = field(pushAndTags, '推荐文案') || '不可得（当前归档未独立保存平台推荐文案）';
  const topicTags = field(pushAndTags, '话题标签') || '不可得（当前归档未独立保存话题标签）';
  const searchTerms = field(pushAndTags, '搜索词') || '不可得（当前归档未记录采集搜索词）';
  const platformTags = field(pushAndTags, '平台标签') || '不可得（当前归档未独立保存平台标签）';
  const trackProblem = field(trackProblemSection, '赛道问题') || field(card, '现实/基础问题') || '待核实（旧拆解卡未形成赛道问题）';
  const topicOriginText = topicOrigin || '加工动作：待核实（旧拆解卡未记录选题加工）';
  const originalTopicText = originalTopic || `原选题：${field(card, '原选题') || '待核实'}`;
  const authorAnswerText = authorAnswer || `作者答案：${field(card, '作者答案') || field(card, '内容答案') || '待核实'}`;
  const spreadReasonText = spreadReason || `传播判断：${field(card, '主要传播判断') || field(card, '候选传播击中点') || '待核实'}\n判断依据：${field(card, '支持证据') || '待核实'}\n证据边界：${field(card, '结论强度') || '旧拆解卡证据边界待复核'}`;
  const takeawayText = takeaway || `最值得拿走：${field(card, '最值得带走') || field(card, '最值得拿走') || '待核实'}`;
  const sourceEvidenceLink = sourceContentPath
    ? `- 原始证据附件：[打开](${relativeFromDetails(sourceContentPath)})`
    : '- 原始证据附件：缺失';
  const detail = `# ${id}｜${title}\n\n内容概览：迁移候选。${compactText(authorAnswerText) || '旧拆解卡没有足够信息形成独立内容概览，待人工重拆。'}\n内容推进：待人工按完整原作复核；迁移脚本不从旧字段推断讲述顺序。\n\n## 01 来源与数据\n\n${sourceForDetail}\n\n- 赛道：${track}\n- 当前详情版本：V2.0-六模块汇总兼容迁移\n- 当前拆解卡：[同版本拆解卡](${relativeFromDetails(cardPath)})\n${sourceEvidenceLink}\n- 全文状态：${fullTextState}\n\n## 02 推送语与推送标签\n\n推送语：${pushCopy}\n推荐文案：${recommendationCopy}\n话题标签：${topicTags}\n搜索词：${searchTerms}\n平台标签：${platformTags}\n证据状态：按当前归档迁移；缺失项未由标题或 AI 代填。\n\n## 03 完整逐字稿\n\n<details>\n<summary>展开完整逐字稿 / 正文 / 逐页 OCR</summary>\n\n${originalText.trim()}\n\n</details>\n\n${sourceOriginal ? `### 原图文归档摘要\n\n${sourceOriginal}\n\n` : ''}关键视觉信息：待核实（迁移脚本不推断视觉）\n\n## 04 赛道问题\n\n赛道问题：${trackProblem}\n问题证据：迁移自同版本拆解卡；旧卡缺真实用户信号时仍需复核。\n\n## 05 选题怎么来的\n\n${topicOriginText}\n\n## 06 原选题\n\n${originalTopicText}\n\n## 07 作者答案\n\n一句话答案：${compactText(authorAnswerText) || '待人工重拆'}\n作者怎样讲清楚：\n${authorAnswerText}\n关键方法或判断：待人工从完整原作复核。\n适用边界：待人工复核。\n\n## 08 为什么能传播\n\n${spreadReasonText}\n\n## 09 评论区洞察\n\n评论验证：${compactText(commentInsight) || '不可得（旧拆解卡没有评论洞察）'}\n\n代表原话：\n${rawComments}\n\n继续长出的问题：待人工从有效评论复核。\n证据边界：按当前归档迁移，不冒充完整评论分布。\n\n## 10 最值得拿走\n\n主要带走：${compactText(takeawayText) || '待人工重拆'}\n具体借法：待当前价值审计后确定。\n暂不借：缺少直接证据或仍待人工复核的部分。\n下一步用途：补证后再判断。\n`;

  const detailPath = path.join(detailsDir, `${id}.md`);
  fs.writeFileSync(detailPath, detail, 'utf8');

  const problem = trackProblem === '待核实（旧拆解卡未形成赛道问题）' ? '' : trackProblem;
  if (problem) problems.push({ text: problem, evidence_state: 'AI归纳，基于完整原作与当前拆解卡', sources: [id] });
  if (topicOrigin) topicArchetypeCandidates.push({
    archetype_id: `ARCHETYPE-CANDIDATE-${String(topicArchetypeCandidates.length + 1).padStart(3, '0')}`,
    types: archetypeTypes(topicOrigin),
    processing_evidence: topicOrigin,
    applicable_track_problem: problem || '待关联',
    representative_topic: originalTopicText,
    sources: [id],
    evidence_state: '原作选题加工识别',
    status: '单样本候选，待跨样本归并'
  });
  if (!/传播判断：待核实/.test(spreadReasonText)) spreadSignalCandidates.push({
    pattern_id: `SPREAD-SIGNAL-${String(spreadSignalCandidates.length + 1).padStart(3, '0')}`,
    spread_signal: spreadReasonText,
    sample_scope: [id],
    sample_count: 1,
    supporting_evidence: '迁移自单条十步拆解卡',
    counterexamples: '待跨样本复核',
    applicability: '待跨样本复核',
    conclusion_strength: '单样本候选',
    status: '待跨样本验证'
  });
  if (!rawComments.startsWith('当前归档没有')) userLanguageCandidates.push({
    language_id: `LANGUAGE-CANDIDATE-${String(userLanguageCandidates.length + 1).padStart(3, '0')}`,
    type: '用户原话',
    original_quote: rawComments,
    user_identity_and_scenario: '待从原评论复核',
    source: id,
    related_track_problem: problem || '待关联',
    topic_clue: commentInsight || '待拆分',
    evidence_state: '迁移自当前可见或代表评论',
    status: '迁移候选，待逐条拆分'
  });
  records.push({
    record_id: id,
    title,
    author,
    platform,
    tracks: [track],
    detail_page: relativeFromDb(detailPath),
    source_url: sourceUrl,
    source_content: sourceContentPath ? relativeFromDb(sourceContentPath) : null,
    comment_source: relativeFromDb(cardPath),
    deconstruction_card: relativeFromDb(cardPath),
    deconstruction_version: 'V2.0-ten-step-six-module-compatible',
    batch_id: path.basename(batchDir),
    full_text_state: fullTextState,
    comment_state: rawComments.startsWith('当前归档没有') ? '缺逐条评论原文' : '已保存当前可见或代表评论',
    manual_confirmation: '样本已确认；拆解待持续人工校准',
    migrated_at: new Date().toISOString()
  });
}

const index = {
  schema_version: 'track-database-v2.0-six-modules',
  generated_at: new Date().toISOString(),
  project_root: projectRoot,
  track,
  rules: {
    summary_modules: ['赛道理解', '赛道问题池', '用户语言与评论问题库', '赛道传播规律'],
    detail_evidence_layer: '单篇十步详情页',
    one_sample_one_record: true,
    source_auto_association: true,
    legacy_four_branch_frontend: false,
    legacy_overview_and_material_list_frontend: false
  },
  records
};

const aggregatedProblems = aggregateProblems(problems);
const backend = {
  schema_version: 'track-database-v3.0-track-understanding',
  generated_at: new Date().toISOString(),
  track,
  track_understanding: '待基于跨样本问题、用户语言、传播规律和作者答案完成行业理解',
  track_problem_pool: aggregatedProblems,
  topic_archetype_library: topicArchetypeCandidates,
  user_language_and_comment_question_library: userLanguageCandidates,
  track_spread_patterns: spreadSignalCandidates,
  aggregation_gaps: {
    problem_deduplication: '脚本只完成精确文本归并，同义问题仍需人工复核',
    track_understanding: '待人工完成跨样本行业归纳',
    topic_archetypes: '全部为单样本候选，待跨样本归并并补充适用条件与反例',
    user_language: '迁移评论可能仍为段落，待按原话、追问、争议与反对逐条拆分',
    spread_patterns: '全部为单样本传播信号，待可比样本跨样本验证'
  }
};

function oneLine(value, maxLength = 180) {
  return compactText(value, maxLength);
}

function listOrEmpty(items, render, emptyText) {
  return items.length ? items.map(render).join('\n') : `- ${emptyText}`;
}

const summaryDraft = `# ${track}｜赛道认知库迁移候选

> 本页由旧库迁移脚本生成，只用于人工复核；不会覆盖正式《赛道与内容数据库》入口。候选状态不得直接当作正式赛道结论。

## 01 赛道理解

- 待基于跨样本问题、用户语言、传播规律和作者答案完成人工归纳。

## 02 赛道问题池

${listOrEmpty(backend.track_problem_pool, (item) => `- ${oneLine(item.track_problem)}｜出现 ${item.occurrence_count} 次｜${item.status}`, '暂无可迁移问题')}

## 03 用户语言与评论问题库

${listOrEmpty(backend.user_language_and_comment_question_library, (item) => `- ${item.type}｜${oneLine(item.original_quote)}｜${item.status}`, '暂无可迁移用户语言')}

## 04 赛道传播规律

${listOrEmpty(backend.track_spread_patterns, (item) => `- ${oneLine(item.spread_signal)}｜${item.status}`, '暂无传播信号候选')}

## 聚合缺口

- 问题归并：${backend.aggregation_gaps.problem_deduplication}
- 赛道理解：${backend.aggregation_gaps.track_understanding}
- 选题母型：${backend.aggregation_gaps.topic_archetypes}
- 用户语言：${backend.aggregation_gaps.user_language}
- 传播规律：${backend.aggregation_gaps.spread_patterns}
`;

fs.writeFileSync(path.join(dbDir, '后台关联索引.json'), JSON.stringify(index, null, 2) + '\n', 'utf8');
fs.writeFileSync(path.join(dbDir, '赛道汇总库.json'), JSON.stringify(backend, null, 2) + '\n', 'utf8');
fs.writeFileSync(path.join(dbDir, '赛道汇总迁移候选.md'), summaryDraft, 'utf8');

console.log(JSON.stringify({
  records: records.length,
  details: records.length,
  track_problems: aggregatedProblems.length,
  topic_archetype_candidates: topicArchetypeCandidates.length,
  user_language_candidates: userLanguageCandidates.length,
  spread_signal_candidates: spreadSignalCandidates.length,
  summary_draft: '赛道数据库/赛道汇总迁移候选.md'
}, null, 2));
