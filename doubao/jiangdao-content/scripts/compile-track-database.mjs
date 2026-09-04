#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const RESPONSE_TYPES = [
  '用户容易认可什么',
  '用户会继续追问什么',
  '用户会质疑或反对什么',
  '这些反应说明什么',
];
const UNDERSTANDING_ASPECTS = new Set([
  'industry_focus',
  'user_interest',
  'monetization',
  'long_term_gap',
]);
const INPUT_STATES = new Set(['full_text', 'transcript_only']);
const TRACK_ROLES = new Set(['core', 'business_contact']);
const PROCESSING_ACTIONS = new Set([
  '未加工',
  '元素迁移',
  '选题具体化',
  '收益显化',
  '损失显化',
  '损益显化',
]);

function argument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : null;
}

const manifestPath = argument('--manifest');
const outputRoot = argument('--out');
const checkOnly = process.argv.includes('--check');

if (!manifestPath || (!outputRoot && !checkOnly)) {
  console.error('usage: compile-track-database.mjs --manifest <编译资料包.json> [--out <空白目录> | --check]');
  process.exit(2);
}

const failures = [];
let manifest;
try {
  manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
} catch (error) {
  console.error(`TRACK_DATABASE_COMPILE_FAILED\nMANIFEST_READ_ERROR ${error.message}`);
  process.exit(1);
}

function text(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function question(value) {
  const valueText = text(value);
  return valueText.length >= 8 && /[？?]$/.test(valueText);
}

function uniqueMap(items, idKey, label) {
  const map = new Map();
  if (!Array.isArray(items)) {
    failures.push(`${label}_INVALID expected array`);
    return map;
  }
  items.forEach((item, index) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      failures.push(`${label}_RECORD_INVALID index=${index}`);
      return;
    }
    const id = text(item[idKey]);
    if (!id) {
      failures.push(`${label}_ID_MISSING index=${index}`);
      return;
    }
    if (map.has(id)) failures.push(`${label}_ID_DUPLICATE ${id}`);
    map.set(id, item);
  });
  return map;
}

function resolveEvidencePath(rawPath, evidenceRoot) {
  if (!text(rawPath)) return null;
  if (path.isAbsolute(rawPath)) return rawPath;
  return path.resolve(evidenceRoot, rawPath);
}

function normalizeQuestion(value) {
  return text(value).replace(/[\s，。！？、；：,.!?;:（）()《》“”"']/g, '').toLowerCase();
}

function idsForTrack(items, trackId) {
  return items.filter((item) => Array.isArray(item.track_ids) && item.track_ids.includes(trackId));
}

function validateTrackIds(item, id, trackMap, label) {
  if (!Array.isArray(item.track_ids) || item.track_ids.length === 0) {
    failures.push(`${label}_TRACKS_MISSING ${id}`);
    return;
  }
  for (const trackId of item.track_ids) {
    if (!trackMap.has(trackId)) failures.push(`${label}_TRACK_UNKNOWN ${id} -> ${trackId}`);
  }
}

if (manifest.schema_version !== 'track-database-compilation-v1') {
  failures.push(`SCHEMA_VERSION_INVALID ${manifest.schema_version || 'missing'}`);
}

const tracks = Array.isArray(manifest.tracks) ? manifest.tracks : [];
const trackMap = uniqueMap(tracks, 'track_id', 'TRACK');
const recordMap = uniqueMap(manifest.source_records, 'record_id', 'SOURCE_RECORD');
const problemMap = uniqueMap(manifest.source_problems, 'source_problem_id', 'SOURCE_PROBLEM');
const answerMap = uniqueMap(manifest.answer_assets || [], 'answer_id', 'ANSWER_ASSET');
const quoteMap = uniqueMap(manifest.comment_quotes || [], 'quote_id', 'COMMENT_QUOTE');
const actionMap = uniqueMap(manifest.topic_processing_actions || [], 'action_id', 'PROCESSING_ACTION');
const signalMap = uniqueMap(manifest.spread_signals || [], 'signal_id', 'SPREAD_SIGNAL');

if (!tracks.length) failures.push('TRACKS_EMPTY');

const manifestDir = path.dirname(path.resolve(manifestPath));
const evidenceRoot = path.resolve(manifestDir, text(manifest.evidence_root) || '.');

for (const [recordId, record] of recordMap) {
  if (!text(record.title)) failures.push(`SOURCE_RECORD_TITLE_MISSING ${recordId}`);
  if (!INPUT_STATES.has(record.input_state)) failures.push(`SOURCE_RECORD_STATE_INVALID ${recordId}: ${record.input_state}`);
  const detailPath = resolveEvidencePath(record.detail_path, evidenceRoot);
  if (!detailPath || !fs.existsSync(detailPath)) failures.push(`SOURCE_RECORD_DETAIL_MISSING ${recordId}: ${record.detail_path || 'missing'}`);
}

const evidenceMaps = [problemMap, answerMap, quoteMap, actionMap, signalMap];
const evidenceIds = new Set(evidenceMaps.flatMap((map) => [...map.keys()]));
const evidenceIndex = new Map(evidenceMaps.flatMap((map) => [...map.entries()]));

for (const [problemId, problem] of problemMap) {
  if (!question(problem.question)) failures.push(`SOURCE_PROBLEM_NOT_QUESTION ${problemId}`);
  if (!recordMap.has(problem.record_id)) failures.push(`SOURCE_PROBLEM_RECORD_UNKNOWN ${problemId} -> ${problem.record_id}`);
  if (!text(problem.evidence_identity)) failures.push(`SOURCE_PROBLEM_EVIDENCE_IDENTITY_MISSING ${problemId}`);
  validateTrackIds(problem, problemId, trackMap, 'SOURCE_PROBLEM');
}

for (const [answerId, answer] of answerMap) {
  if (!text(answer.text)) failures.push(`ANSWER_TEXT_MISSING ${answerId}`);
  if (!recordMap.has(answer.record_id)) failures.push(`ANSWER_RECORD_UNKNOWN ${answerId} -> ${answer.record_id}`);
  validateTrackIds(answer, answerId, trackMap, 'ANSWER');
}

for (const [quoteId, quote] of quoteMap) {
  if (!text(quote.quote)) failures.push(`COMMENT_QUOTE_TEXT_MISSING ${quoteId}`);
  if (!recordMap.has(quote.record_id)) failures.push(`COMMENT_QUOTE_RECORD_UNKNOWN ${quoteId} -> ${quote.record_id}`);
  if (quote.evidence_status !== 'real_user_quote') failures.push(`COMMENT_QUOTE_NOT_REAL ${quoteId}`);
  if (!RESPONSE_TYPES.slice(0, 3).includes(quote.response_type)) failures.push(`COMMENT_RESPONSE_TYPE_INVALID ${quoteId}: ${quote.response_type}`);
  const evidencePath = resolveEvidencePath(quote.evidence_path, evidenceRoot);
  if (!evidencePath || !fs.existsSync(evidencePath)) failures.push(`COMMENT_EVIDENCE_MISSING ${quoteId}: ${quote.evidence_path || 'missing'}`);
  validateTrackIds(quote, quoteId, trackMap, 'COMMENT_QUOTE');
}

for (const [actionId, action] of actionMap) {
  if (!PROCESSING_ACTIONS.has(action.action)) failures.push(`PROCESSING_ACTION_INVALID ${actionId}: ${action.action}`);
  if (!recordMap.has(action.record_id)) failures.push(`PROCESSING_RECORD_UNKNOWN ${actionId} -> ${action.record_id}`);
  if (!text(action.evidence_quote)) failures.push(`PROCESSING_EVIDENCE_MISSING ${actionId}`);
  validateTrackIds(action, actionId, trackMap, 'PROCESSING_ACTION');
}

for (const [signalId, signal] of signalMap) {
  if (!text(signal.text) || !text(signal.evidence_basis)) failures.push(`SPREAD_SIGNAL_INCOMPLETE ${signalId}`);
  if (!recordMap.has(signal.record_id)) failures.push(`SPREAD_SIGNAL_RECORD_UNKNOWN ${signalId} -> ${signal.record_id}`);
  validateTrackIds(signal, signalId, trackMap, 'SPREAD_SIGNAL');
}

const coreKeywords = Array.isArray(manifest.core_track_keywords)
  ? manifest.core_track_keywords.map(text).filter(Boolean)
  : [];
if (coreKeywords.length < 1 || coreKeywords.length > 3 || new Set(coreKeywords).size !== coreKeywords.length) {
  failures.push('CORE_TRACK_KEYWORDS_INVALID expected 1-3 unique values');
}
const declaredCoreKeywords = new Set(tracks
  .filter((track) => track.role === 'core')
  .map((track) => text(track.confirmed_keyword))
  .filter(Boolean));
for (const keyword of coreKeywords) {
  if (!declaredCoreKeywords.has(keyword)) failures.push(`CORE_TRACK_KEYWORD_WITHOUT_TRACK ${keyword}`);
}

const referencedRecordIds = new Set();
const compiledTracks = {};

for (const [trackId, track] of trackMap) {
  if (!text(track.display_name)) failures.push(`TRACK_DISPLAY_NAME_MISSING ${trackId}`);
  if (!TRACK_ROLES.has(track.role)) failures.push(`TRACK_ROLE_INVALID ${trackId}: ${track.role}`);
  if (track.role === 'core') {
    if (!text(track.confirmed_keyword)) failures.push(`CORE_TRACK_KEYWORD_MISSING ${trackId}`);
    if (!coreKeywords.includes(text(track.confirmed_keyword))) failures.push(`CORE_TRACK_KEYWORD_NOT_CONFIRMED ${trackId}: ${track.confirmed_keyword}`);
  }
  if (track.role === 'business_contact' && coreKeywords.includes(text(track.confirmed_keyword || track.display_name))) {
    failures.push(`BUSINESS_TRACK_MIXED_IN_CORE ${trackId}`);
  }

  const sourceRecordIds = Array.isArray(track.source_record_ids) ? track.source_record_ids : [];
  if (!sourceRecordIds.length) failures.push(`TRACK_SOURCE_RECORDS_EMPTY ${trackId}`);
  const sourceRecordSet = new Set();
  for (const recordId of sourceRecordIds) {
    if (!recordMap.has(recordId)) failures.push(`TRACK_SOURCE_RECORD_UNKNOWN ${trackId} -> ${recordId}`);
    if (sourceRecordSet.has(recordId)) failures.push(`TRACK_SOURCE_RECORD_DUPLICATE ${trackId} -> ${recordId}`);
    sourceRecordSet.add(recordId);
    referencedRecordIds.add(recordId);
  }

  for (const evidence of [
    ...idsForTrack([...problemMap.values()], trackId),
    ...idsForTrack([...answerMap.values()], trackId),
    ...idsForTrack([...quoteMap.values()], trackId),
    ...idsForTrack([...actionMap.values()], trackId),
    ...idsForTrack([...signalMap.values()], trackId),
  ]) {
    if (!sourceRecordSet.has(evidence.record_id)) {
      failures.push(`TRACK_EVIDENCE_RECORD_NOT_INCLUDED ${trackId}:${evidence.record_id}`);
    }
  }

  const trackProblems = idsForTrack([...problemMap.values()], trackId)
    .filter((item) => sourceRecordSet.has(item.record_id));
  const eligibleProblemIds = new Set(trackProblems.map((item) => item.source_problem_id));
  const consumedProblemIds = new Set();
  const problemGroups = Array.isArray(track.problem_groups) ? track.problem_groups : [];
  const groupIds = new Set();
  const normalizedQuestions = new Set();

  for (const [index, group] of problemGroups.entries()) {
    const groupId = text(group.problem_id);
    if (!groupId) failures.push(`PROBLEM_GROUP_ID_MISSING ${trackId}[${index}]`);
    if (groupIds.has(groupId)) failures.push(`PROBLEM_GROUP_ID_DUPLICATE ${trackId}:${groupId}`);
    groupIds.add(groupId);
    if (!question(group.question)) failures.push(`PROBLEM_GROUP_NOT_QUESTION ${trackId}:${groupId}`);
    const normalized = normalizeQuestion(group.question);
    if (normalizedQuestions.has(normalized)) failures.push(`PROBLEM_GROUP_DUPLICATE_TEXT ${trackId}:${group.question}`);
    normalizedQuestions.add(normalized);
    const sourceProblemIds = Array.isArray(group.source_problem_ids) ? group.source_problem_ids : [];
    if (!sourceProblemIds.length) failures.push(`PROBLEM_GROUP_SOURCES_EMPTY ${trackId}:${groupId}`);
    for (const sourceProblemId of sourceProblemIds) {
      if (!eligibleProblemIds.has(sourceProblemId)) failures.push(`PROBLEM_GROUP_SOURCE_INVALID ${trackId}:${groupId} -> ${sourceProblemId}`);
      if (consumedProblemIds.has(sourceProblemId)) failures.push(`SOURCE_PROBLEM_USED_TWICE ${trackId}:${sourceProblemId}`);
      consumedProblemIds.add(sourceProblemId);
    }
    const audit = group.merge_audit || {};
    if (!text(audit.shared_core_need) || !text(audit.reason)) failures.push(`PROBLEM_MERGE_AUDIT_INCOMPLETE ${trackId}:${groupId}`);
    if (audit.differences_change_answer !== false) failures.push(`PROBLEM_MERGE_ANSWER_BOUNDARY_FAILED ${trackId}:${groupId}`);
  }

  const excluded = Array.isArray(track.excluded_source_problems) ? track.excluded_source_problems : [];
  for (const item of excluded) {
    const sourceProblemId = text(item.source_problem_id);
    if (!eligibleProblemIds.has(sourceProblemId)) failures.push(`EXCLUDED_SOURCE_PROBLEM_INVALID ${trackId}:${sourceProblemId}`);
    if (!text(item.reason)) failures.push(`EXCLUDED_SOURCE_PROBLEM_REASON_MISSING ${trackId}:${sourceProblemId}`);
    if (consumedProblemIds.has(sourceProblemId)) failures.push(`SOURCE_PROBLEM_USED_TWICE ${trackId}:${sourceProblemId}`);
    consumedProblemIds.add(sourceProblemId);
  }
  for (const sourceProblemId of eligibleProblemIds) {
    if (!consumedProblemIds.has(sourceProblemId)) failures.push(`SOURCE_PROBLEM_UNASSIGNED ${trackId}:${sourceProblemId}`);
  }

  const paragraphs = track.understanding?.paragraphs;
  if (!Array.isArray(paragraphs) || paragraphs.length < 1 || paragraphs.length > 3) {
    failures.push(`TRACK_UNDERSTANDING_PARAGRAPHS_INVALID ${trackId}`);
  }
  const coveredAspects = new Set();
  for (const [index, paragraph] of (paragraphs || []).entries()) {
    if (text(paragraph.text).length < 20) failures.push(`TRACK_UNDERSTANDING_TEXT_TOO_SHORT ${trackId}[${index}]`);
    const aspects = Array.isArray(paragraph.aspects) ? paragraph.aspects : [];
    for (const aspect of aspects) {
      if (!UNDERSTANDING_ASPECTS.has(aspect)) failures.push(`TRACK_UNDERSTANDING_ASPECT_INVALID ${trackId}:${aspect}`);
      coveredAspects.add(aspect);
    }
    const ids = Array.isArray(paragraph.evidence_ids) ? paragraph.evidence_ids : [];
    if (!ids.length) failures.push(`TRACK_UNDERSTANDING_EVIDENCE_EMPTY ${trackId}[${index}]`);
    for (const id of ids) {
      const evidence = evidenceIndex.get(id);
      if (!evidenceIds.has(id)) {
        failures.push(`TRACK_UNDERSTANDING_EVIDENCE_UNKNOWN ${trackId}:${id}`);
      } else if (!evidence.track_ids?.includes(trackId) || !sourceRecordSet.has(evidence.record_id)) {
        failures.push(`TRACK_UNDERSTANDING_EVIDENCE_WRONG_TRACK ${trackId}:${id}`);
      }
    }
  }
  for (const aspect of UNDERSTANDING_ASPECTS) {
    if (!coveredAspects.has(aspect)) failures.push(`TRACK_UNDERSTANDING_ASPECT_MISSING ${trackId}:${aspect}`);
  }

  const responseMap = track.user_response_map || {};
  if (!['verified', 'unavailable'].includes(responseMap.status)) failures.push(`USER_RESPONSE_STATUS_INVALID ${trackId}`);
  if (responseMap.status === 'unavailable') {
    if (!text(responseMap.reason)) failures.push(`USER_RESPONSE_UNAVAILABLE_REASON_MISSING ${trackId}`);
    if (Array.isArray(responseMap.sections) && responseMap.sections.length) failures.push(`USER_RESPONSE_UNAVAILABLE_HAS_SECTIONS ${trackId}`);
  } else if (responseMap.status === 'verified') {
    const sections = Array.isArray(responseMap.sections) ? responseMap.sections : [];
    if (sections.length !== RESPONSE_TYPES.length) failures.push(`USER_RESPONSE_SECTION_COUNT_INVALID ${trackId}`);
    sections.forEach((section, index) => {
      if (section.type !== RESPONSE_TYPES[index]) failures.push(`USER_RESPONSE_SECTION_ORDER_INVALID ${trackId}[${index}]`);
      const insights = Array.isArray(section.insights) ? section.insights : [];
      if (!insights.length) failures.push(`USER_RESPONSE_INSIGHTS_EMPTY ${trackId}:${section.type}`);
      insights.forEach((insight, insightIndex) => {
        if (!text(insight.text)) failures.push(`USER_RESPONSE_INSIGHT_TEXT_MISSING ${trackId}:${section.type}[${insightIndex}]`);
        const quoteIds = Array.isArray(insight.quote_ids) ? insight.quote_ids : [];
        if (!quoteIds.length) failures.push(`USER_RESPONSE_QUOTE_IDS_EMPTY ${trackId}:${section.type}[${insightIndex}]`);
        for (const quoteId of quoteIds) {
          const quote = quoteMap.get(quoteId);
          if (!quote || !quote.track_ids?.includes(trackId) || !sourceRecordSet.has(quote.record_id)) {
            failures.push(`USER_RESPONSE_QUOTE_INVALID ${trackId}:${quoteId}`);
          } else if (index < 3 && quote.response_type !== section.type) {
            failures.push(`USER_RESPONSE_QUOTE_TYPE_MISMATCH ${trackId}:${section.type} -> ${quoteId}`);
          }
        }
      });
    });
  }

  const spreadPatterns = Array.isArray(track.spread_patterns) ? track.spread_patterns : [];
  const patternIds = new Set();
  for (const patternItem of spreadPatterns) {
    const patternId = text(patternItem.pattern_id);
    if (!patternId || patternIds.has(patternId)) failures.push(`SPREAD_PATTERN_ID_INVALID ${trackId}:${patternId || 'missing'}`);
    patternIds.add(patternId);
    if (!text(patternItem.text) || !text(patternItem.scope) || !text(patternItem.evidence_boundary)) failures.push(`SPREAD_PATTERN_INCOMPLETE ${trackId}:${patternId}`);
    const signalIds = Array.isArray(patternItem.signal_ids) ? patternItem.signal_ids : [];
    const signalRecordIds = new Set();
    for (const signalId of signalIds) {
      const signal = signalMap.get(signalId);
      if (!signal || !signal.track_ids?.includes(trackId) || !sourceRecordSet.has(signal.record_id)) {
        failures.push(`SPREAD_PATTERN_SIGNAL_INVALID ${trackId}:${patternId} -> ${signalId}`);
      } else {
        signalRecordIds.add(signal.record_id);
      }
    }
    if (signalRecordIds.size < 2) failures.push(`SPREAD_PATTERN_NOT_CROSS_SAMPLE ${trackId}:${patternId}`);
  }

  const processingLibrary = Array.isArray(track.topic_processing_library) ? track.topic_processing_library : [];
  const libraryIds = new Set();
  for (const library of processingLibrary) {
    const libraryId = text(library.library_id);
    if (!libraryId || libraryIds.has(libraryId)) failures.push(`PROCESSING_LIBRARY_ID_INVALID ${trackId}:${libraryId || 'missing'}`);
    libraryIds.add(libraryId);
    if (!PROCESSING_ACTIONS.has(library.action)) failures.push(`PROCESSING_LIBRARY_ACTION_INVALID ${trackId}:${libraryId}`);
    if (!text(library.applicable_condition) || !text(library.boundary)) failures.push(`PROCESSING_LIBRARY_BOUNDARY_MISSING ${trackId}:${libraryId}`);
    const sourceActionIds = Array.isArray(library.source_action_ids) ? library.source_action_ids : [];
    if (!sourceActionIds.length) failures.push(`PROCESSING_LIBRARY_SOURCES_EMPTY ${trackId}:${libraryId}`);
    for (const actionId of sourceActionIds) {
      const action = actionMap.get(actionId);
      if (!action || !action.track_ids?.includes(trackId) || !sourceRecordSet.has(action.record_id)) {
        failures.push(`PROCESSING_LIBRARY_SOURCE_INVALID ${trackId}:${libraryId} -> ${actionId}`);
      }
    }
  }

  compiledTracks[trackId] = {
    schema_version: 'track-database-v4.0-generic',
    track_id: trackId,
    track: track.display_name,
    track_role: track.role,
    confirmed_keyword: track.role === 'core' ? track.confirmed_keyword : null,
    track_understanding: {
      paragraphs: (paragraphs || []).map((item) => ({
        text: item.text,
        aspects: item.aspects,
        evidence_ids: item.evidence_ids,
      })),
    },
    track_problem_pool: problemGroups.map((item) => ({
      problem_id: item.problem_id,
      problem: item.question,
      source_problem_ids: item.source_problem_ids,
      merge_audit: item.merge_audit,
      sources: [...new Set(item.source_problem_ids.map((id) => problemMap.get(id)?.record_id).filter(Boolean))],
    })),
    topic_archetype_library: processingLibrary.map((item) => ({ ...item })),
    user_language_and_comment_question_library: idsForTrack([...quoteMap.values()], trackId)
      .filter((item) => sourceRecordSet.has(item.record_id)),
    user_response_map: responseMap,
    track_spread_patterns: spreadPatterns.map((item) => ({ ...item })),
    aggregation_gaps: track.aggregation_gaps && typeof track.aggregation_gaps === 'object'
      ? track.aggregation_gaps
      : {},
    source_records: sourceRecordIds.map((id) => recordMap.get(id)).filter(Boolean),
  };
}

for (const recordId of recordMap.keys()) {
  if (!referencedRecordIds.has(recordId)) failures.push(`SOURCE_RECORD_UNASSIGNED ${recordId}`);
}

if (failures.length) {
  console.error('TRACK_DATABASE_COMPILE_FAILED');
  console.error(failures.join('\n'));
  process.exit(1);
}

function heading(level, value) {
  return `${'#'.repeat(level)} ${value}`;
}

function renderResponseMap(responseMap, level, quotes) {
  if (responseMap.status === 'unavailable') {
    return [`评论证据暂不可得：${responseMap.reason}`];
  }
  const lines = [];
  for (const section of responseMap.sections) {
    lines.push(heading(level, section.type), '');
    for (const insight of section.insights) {
      lines.push(`- ${insight.text}`);
      const representative = quotes.get(insight.quote_ids[0]);
      if (representative) lines.push(`  > “${representative.quote}”`);
    }
    lines.push('');
  }
  return lines;
}

function renderTrack(trackId, track, moduleLevel) {
  const compiled = compiledTracks[trackId];
  const lines = [];
  lines.push(heading(moduleLevel, '01 赛道理解'), '');
  for (const paragraph of compiled.track_understanding.paragraphs) lines.push(paragraph.text, '');
  lines.push(heading(moduleLevel, '02 赛道问题池'), '');
  for (const item of compiled.track_problem_pool) lines.push(`- ${item.problem}`);
  lines.push('', heading(moduleLevel, '03 用户语言与评论问题库'), '');
  lines.push(...renderResponseMap(compiled.user_response_map, moduleLevel + 1, quoteMap));
  lines.push('', heading(moduleLevel, '04 赛道传播规律'), '');
  if (compiled.track_spread_patterns.length) {
    for (const item of compiled.track_spread_patterns) lines.push(`- ${item.text}`);
  } else {
    lines.push('当前还没有足够的跨样本证据形成稳定传播规律。');
  }
  return lines;
}

function slug(value) {
  return value.replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]+/g, '-').replace(/^-+|-+$/g, '') || 'track';
}

const trackPagePaths = {};
for (const [trackId, track] of trackMap) {
  trackPagePaths[trackId] = `赛道数据库/${slug(trackId)}/赛道数据库.md`;
}

const rootDatabase = {
  schema_version: 'track-database-v4.0-generic',
  generated_at: new Date().toISOString(),
  core_track_keywords: coreKeywords,
  track_groups: {
    core: tracks.filter((item) => item.role === 'core').map((item) => item.track_id),
    business_contact: tracks.filter((item) => item.role === 'business_contact').map((item) => item.track_id),
  },
  track_pages: trackPagePaths,
  tracks: compiledTracks,
  source_records: [...recordMap.values()],
  evidence_catalogs: {
    source_problems: [...problemMap.values()],
    answer_assets: [...answerMap.values()],
    comment_quotes: [...quoteMap.values()],
    topic_processing_actions: [...actionMap.values()],
    spread_signals: [...signalMap.values()],
  },
  backend_associations: Object.fromEntries([...recordMap.keys()].map((recordId) => [
    recordId,
    tracks.filter((track) => track.source_record_ids.includes(recordId)).map((track) => track.track_id),
  ])),
};

const rootLines = [
  '# 赛道数据库',
  '',
  `核心赛道词：${coreKeywords.join('、')}`,
  '',
];

const groups = [
  ['自己持续经营的赛道', 'core'],
  ['工作中接触的赛道', 'business_contact'],
];
for (const [groupTitle, role] of groups) {
  const groupTracks = tracks.filter((item) => item.role === role);
  if (!groupTracks.length) continue;
  rootLines.push(`## ${groupTitle}`, '');
  if (role === 'business_contact') {
    rootLines.push('这些赛道用于理解工作中接触的用户行业，不自动进入当前 IP 的选题共创。', '');
  }
  for (const track of groupTracks) {
    rootLines.push(`### ${track.display_name}`, '');
    rootLines.push(...renderTrack(track.track_id, track, 4), '');
  }
}

if (checkOnly) {
  console.log(`TRACK_DATABASE_COMPILE_CHECK_OK tracks=${tracks.length} records=${recordMap.size}`);
  process.exit(0);
}

const resolvedOutput = path.resolve(outputRoot);
if (fs.existsSync(resolvedOutput) && fs.readdirSync(resolvedOutput).length > 0) {
  console.error(`TRACK_DATABASE_COMPILE_FAILED\nOUTPUT_NOT_EMPTY ${resolvedOutput}`);
  process.exit(1);
}
fs.mkdirSync(resolvedOutput, { recursive: true });
const databaseDir = path.join(resolvedOutput, '赛道数据库');
fs.mkdirSync(databaseDir, { recursive: true });

fs.writeFileSync(path.join(resolvedOutput, '赛道数据库.md'), `${rootLines.join('\n').trim()}\n`, 'utf8');
fs.writeFileSync(path.join(databaseDir, '赛道汇总库.json'), `${JSON.stringify(rootDatabase, null, 2)}\n`, 'utf8');
fs.writeFileSync(path.join(databaseDir, '后台关联索引.json'), `${JSON.stringify({
  schema_version: 'track-database-association-v1',
  records: rootDatabase.backend_associations,
  track_pages: trackPagePaths,
}, null, 2)}\n`, 'utf8');

for (const [trackId, track] of trackMap) {
  const trackDir = path.join(databaseDir, slug(trackId));
  fs.mkdirSync(trackDir, { recursive: true });
  const pageLines = [
    `# ${track.display_name}`,
    '',
    ...(track.role === 'business_contact'
      ? ['这一赛道用于理解工作中接触的用户行业，不自动进入当前 IP 的选题共创。', '']
      : []),
    ...renderTrack(trackId, track, 2),
  ];
  fs.writeFileSync(path.join(trackDir, '赛道数据库.md'), `${pageLines.join('\n').trim()}\n`, 'utf8');
  fs.writeFileSync(path.join(trackDir, '赛道汇总库.json'), `${JSON.stringify(compiledTracks[trackId], null, 2)}\n`, 'utf8');
}

console.log(`TRACK_DATABASE_COMPILE_OK tracks=${tracks.length} records=${recordMap.size} out=${resolvedOutput}`);
