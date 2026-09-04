#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const [jsonPath, summaryPath] = process.argv.slice(2);

if (!jsonPath) {
  console.error('usage: validate-track-database-v2.mjs <赛道汇总库.json> [赛道汇总页.md]');
  process.exit(2);
}

const failures = [];
let data;
try {
  data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
} catch (error) {
  console.error(`TRACK_DATABASE_VALIDATION_FAILED\nJSON_READ_ERROR ${error.message}`);
  process.exit(1);
}

function valueText(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function isQuestion(value) {
  const current = valueText(value);
  return current.length >= 8 && /[？?]$/.test(current);
}

function normalized(value) {
  return valueText(value).replace(/[\s，。！？、；：,.!?;:（）()《》“”"']/g, '').toLowerCase();
}

function uniqueIds(items, key, label) {
  const ids = new Set();
  if (!Array.isArray(items)) {
    failures.push(`${label}_INVALID expected array`);
    return ids;
  }
  items.forEach((item, index) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      failures.push(`${label}_RECORD_INVALID index=${index}`);
      return;
    }
    const id = valueText(item[key]);
    if (!id) failures.push(`${label}_ID_MISSING index=${index}`);
    if (ids.has(id)) failures.push(`${label}_ID_DUPLICATE ${id}`);
    ids.add(id);
  });
  return ids;
}

function checkForbiddenFrontstage(summary) {
  const forbidden = [
    '选题母型库',
    '高价值选题池',
    '当前内容机会',
    '题面中的身份、经历、成绩属于谁',
    '当前IP是否有证据承载',
    '是否明确标注为第三方案例',
    '禁止自动迁移给当前IP',
    '证据状态：',
    '当前状态：',
    '运行日志',
  ];
  for (const phrase of forbidden) {
    if (summary.includes(phrase)) failures.push(`FRONTSTAGE_FORBIDDEN ${phrase}`);
  }
}

function validateLegacy() {
  const backendModules = [
    ['track_problem_pool', 'problem_id'],
    ['topic_archetype_library', 'archetype_id'],
    ['user_language_and_comment_question_library', 'language_id'],
    ['track_spread_patterns', 'pattern_id'],
  ];
  const legacyKeys = [
    'topic_processing_pool',
    'spread_judgment_pool',
    'track_overview',
    'viral_materials',
    'content_gaps',
    'high_value_topic_pool',
    'current_content_opportunities',
    'identity_audit',
  ];

  for (const [key, idKey] of backendModules) uniqueIds(data[key], idKey, key.toUpperCase());
  if (!data.aggregation_gaps || typeof data.aggregation_gaps !== 'object' || Array.isArray(data.aggregation_gaps)) {
    failures.push('AGGREGATION_GAPS_INVALID expected object');
  }
  if (!data.track_understanding || (typeof data.track_understanding !== 'string' && typeof data.track_understanding !== 'object')) {
    failures.push('TRACK_UNDERSTANDING_INVALID expected string or object');
  }
  for (const key of legacyKeys) {
    if (Object.hasOwn(data, key)) failures.push(`LEGACY_KEY_PRESENT ${key}`);
  }

  if (summaryPath) {
    let summary = '';
    try {
      summary = fs.readFileSync(summaryPath, 'utf8');
    } catch (error) {
      failures.push(`SUMMARY_READ_ERROR ${error.message}`);
    }
    const headings = ['01 赛道理解', '02 赛道问题池', '03 用户语言与评论问题库', '04 赛道传播规律'];
    let previous = -1;
    for (const heading of headings) {
      const current = summary.indexOf(`## ${heading}`);
      if (current < 0) failures.push(`SUMMARY_HEADING_MISSING ${heading}`);
      if (current >= 0 && current <= previous) failures.push(`SUMMARY_ORDER_INVALID ${heading}`);
      previous = current;
    }
    checkForbiddenFrontstage(summary);
  }
}

function segmentForTrack(summary, displayName) {
  const marker = `### ${displayName}`;
  const start = summary.indexOf(marker);
  if (start < 0) return '';
  const after = start + marker.length;
  const nextTrack = summary.indexOf('\n### ', after);
  const nextGroup = summary.indexOf('\n## ', after);
  const candidates = [nextTrack, nextGroup].filter((index) => index >= 0);
  const end = candidates.length ? Math.min(...candidates) : summary.length;
  return summary.slice(start, end);
}

function validateTrackPage(pagePath, track) {
  let page = '';
  try {
    page = fs.readFileSync(pagePath, 'utf8');
  } catch (error) {
    failures.push(`TRACK_PAGE_READ_ERROR ${track.track_id}: ${error.message}`);
    return;
  }
  if (!page.startsWith(`# ${track.track}\n`)) failures.push(`TRACK_PAGE_TITLE_INVALID ${track.track_id}`);
  const headings = ['01 赛道理解', '02 赛道问题池', '03 用户语言与评论问题库', '04 赛道传播规律'];
  let previous = -1;
  for (const heading of headings) {
    const current = page.indexOf(`## ${heading}`);
    if (current < 0) failures.push(`TRACK_PAGE_HEADING_MISSING ${track.track_id}:${heading}`);
    if (current >= 0 && current <= previous) failures.push(`TRACK_PAGE_ORDER_INVALID ${track.track_id}:${heading}`);
    previous = current;
  }
  checkForbiddenFrontstage(page);
}

function validateV4() {
  const tracks = data.tracks && typeof data.tracks === 'object' && !Array.isArray(data.tracks)
    ? data.tracks
    : {};
  const trackEntries = Object.entries(tracks);
  if (!trackEntries.length) failures.push('TRACKS_EMPTY');

  const coreKeywords = Array.isArray(data.core_track_keywords) ? data.core_track_keywords : [];
  if (coreKeywords.length < 1 || coreKeywords.length > 3 || new Set(coreKeywords).size !== coreKeywords.length) {
    failures.push('CORE_TRACK_KEYWORDS_INVALID');
  }
  const groupCore = Array.isArray(data.track_groups?.core) ? data.track_groups.core : [];
  const groupBusiness = Array.isArray(data.track_groups?.business_contact) ? data.track_groups.business_contact : [];
  const grouped = [...groupCore, ...groupBusiness];
  if (new Set(grouped).size !== grouped.length) failures.push('TRACK_GROUP_DUPLICATE');
  for (const trackId of Object.keys(tracks)) {
    if (!grouped.includes(trackId)) failures.push(`TRACK_GROUP_MISSING ${trackId}`);
  }
  for (const trackId of grouped) {
    if (!tracks[trackId]) failures.push(`TRACK_GROUP_UNKNOWN ${trackId}`);
  }

  const sourceProblemIds = uniqueIds(data.evidence_catalogs?.source_problems, 'source_problem_id', 'SOURCE_PROBLEM');
  const commentQuoteIds = uniqueIds(data.evidence_catalogs?.comment_quotes, 'quote_id', 'COMMENT_QUOTE');
  const processingActionIds = uniqueIds(data.evidence_catalogs?.topic_processing_actions, 'action_id', 'PROCESSING_ACTION');
  const spreadSignals = Array.isArray(data.evidence_catalogs?.spread_signals) ? data.evidence_catalogs.spread_signals : [];
  const spreadSignalIds = uniqueIds(spreadSignals, 'signal_id', 'SPREAD_SIGNAL');
  const spreadSignalById = new Map(spreadSignals.map((item) => [item.signal_id, item]));
  const commentById = new Map((data.evidence_catalogs?.comment_quotes || []).map((item) => [item.quote_id, item]));

  for (const [trackId, track] of trackEntries) {
    if (track.track_id !== trackId) failures.push(`TRACK_ID_MISMATCH ${trackId}`);
    if (!['core', 'business_contact'].includes(track.track_role)) failures.push(`TRACK_ROLE_INVALID ${trackId}`);
    if (track.track_role === 'core' && !coreKeywords.includes(track.confirmed_keyword)) failures.push(`CORE_TRACK_KEYWORD_MISMATCH ${trackId}`);
    if (track.track_role === 'business_contact' && coreKeywords.includes(track.confirmed_keyword || track.track)) {
      failures.push(`BUSINESS_TRACK_MIXED_IN_CORE ${trackId}`);
    }

    const paragraphs = track.track_understanding?.paragraphs;
    if (!Array.isArray(paragraphs) || paragraphs.length < 1 || paragraphs.length > 3) failures.push(`TRACK_UNDERSTANDING_INVALID ${trackId}`);
    const aspects = new Set((paragraphs || []).flatMap((item) => item.aspects || []));
    for (const aspect of ['industry_focus', 'user_interest', 'monetization', 'long_term_gap']) {
      if (!aspects.has(aspect)) failures.push(`TRACK_UNDERSTANDING_ASPECT_MISSING ${trackId}:${aspect}`);
    }

    const problemIds = uniqueIds(track.track_problem_pool, 'problem_id', `PROBLEM_${trackId}`);
    const questions = new Set();
    for (const problem of track.track_problem_pool || []) {
      if (!isQuestion(problem.problem)) failures.push(`PROBLEM_NOT_QUESTION ${trackId}:${problem.problem_id}`);
      const key = normalized(problem.problem);
      if (questions.has(key)) failures.push(`PROBLEM_DUPLICATE_TEXT ${trackId}:${problem.problem}`);
      questions.add(key);
      if (!Array.isArray(problem.source_problem_ids) || !problem.source_problem_ids.length) failures.push(`PROBLEM_SOURCE_EMPTY ${trackId}:${problem.problem_id}`);
      for (const sourceId of problem.source_problem_ids || []) {
        if (!sourceProblemIds.has(sourceId)) failures.push(`PROBLEM_SOURCE_UNKNOWN ${trackId}:${problem.problem_id} -> ${sourceId}`);
      }
      if (!valueText(problem.merge_audit?.shared_core_need) || !valueText(problem.merge_audit?.reason) || problem.merge_audit?.differences_change_answer !== false) {
        failures.push(`PROBLEM_MERGE_AUDIT_INVALID ${trackId}:${problem.problem_id}`);
      }
    }
    if (!problemIds.size) failures.push(`PROBLEM_POOL_EMPTY ${trackId}`);

    const quoteLibraryIds = uniqueIds(track.user_language_and_comment_question_library, 'quote_id', `TRACK_QUOTES_${trackId}`);
    for (const quoteId of quoteLibraryIds) {
      if (!commentQuoteIds.has(quoteId)) failures.push(`TRACK_QUOTE_UNKNOWN ${trackId}:${quoteId}`);
      if (commentById.get(quoteId)?.evidence_status !== 'real_user_quote') failures.push(`TRACK_QUOTE_NOT_REAL ${trackId}:${quoteId}`);
    }
    const responseMap = track.user_response_map || {};
    if (!['verified', 'unavailable'].includes(responseMap.status)) failures.push(`USER_RESPONSE_STATUS_INVALID ${trackId}`);
    if (responseMap.status === 'verified') {
      const expectedTypes = ['用户容易认可什么', '用户会继续追问什么', '用户会质疑或反对什么', '这些反应说明什么'];
      const sections = Array.isArray(responseMap.sections) ? responseMap.sections : [];
      if (sections.length !== expectedTypes.length) failures.push(`USER_RESPONSE_SECTION_COUNT_INVALID ${trackId}`);
      sections.forEach((section, index) => {
        if (section.type !== expectedTypes[index]) failures.push(`USER_RESPONSE_SECTION_ORDER_INVALID ${trackId}[${index}]`);
        for (const insight of section.insights || []) {
          if (!valueText(insight.text) || !Array.isArray(insight.quote_ids) || !insight.quote_ids.length) failures.push(`USER_RESPONSE_INSIGHT_INVALID ${trackId}:${section.type}`);
          for (const quoteId of insight.quote_ids || []) {
            if (!quoteLibraryIds.has(quoteId)) failures.push(`USER_RESPONSE_QUOTE_UNKNOWN ${trackId}:${quoteId}`);
          }
        }
      });
    } else if (!valueText(responseMap.reason)) {
      failures.push(`USER_RESPONSE_UNAVAILABLE_REASON_MISSING ${trackId}`);
    }

    uniqueIds(track.topic_archetype_library, 'library_id', `PROCESSING_LIBRARY_${trackId}`);
    for (const item of track.topic_archetype_library || []) {
      for (const sourceId of item.source_action_ids || []) {
        if (!processingActionIds.has(sourceId)) failures.push(`PROCESSING_SOURCE_UNKNOWN ${trackId}:${sourceId}`);
      }
    }

    uniqueIds(track.track_spread_patterns, 'pattern_id', `SPREAD_PATTERN_${trackId}`);
    for (const pattern of track.track_spread_patterns || []) {
      const recordIds = new Set();
      for (const signalId of pattern.signal_ids || []) {
        if (!spreadSignalIds.has(signalId)) failures.push(`SPREAD_PATTERN_SIGNAL_UNKNOWN ${trackId}:${signalId}`);
        const recordId = spreadSignalById.get(signalId)?.record_id;
        if (recordId) recordIds.add(recordId);
      }
      if (recordIds.size < 2) failures.push(`SPREAD_PATTERN_NOT_CROSS_SAMPLE ${trackId}:${pattern.pattern_id}`);
    }
  }

  if (summaryPath) {
    let summary = '';
    try {
      summary = fs.readFileSync(summaryPath, 'utf8');
    } catch (error) {
      failures.push(`SUMMARY_READ_ERROR ${error.message}`);
    }
    if (!summary.startsWith('# 赛道数据库\n')) failures.push('SUMMARY_TITLE_INVALID');
    if (!summary.includes(`核心赛道词：${coreKeywords.join('、')}`)) failures.push('SUMMARY_CORE_KEYWORDS_MISMATCH');
    checkForbiddenFrontstage(summary);

    const coreIndex = summary.indexOf('## 自己持续经营的赛道');
    const businessIndex = summary.indexOf('## 工作中接触的赛道');
    if (groupCore.length && coreIndex < 0) failures.push('SUMMARY_CORE_GROUP_MISSING');
    if (groupBusiness.length && businessIndex < 0) failures.push('SUMMARY_BUSINESS_GROUP_MISSING');
    if (coreIndex >= 0 && businessIndex >= 0 && coreIndex > businessIndex) failures.push('SUMMARY_GROUP_ORDER_INVALID');

    for (const [trackId, track] of trackEntries) {
      const segment = segmentForTrack(summary, track.track);
      if (!segment) {
        failures.push(`SUMMARY_TRACK_MISSING ${trackId}`);
        continue;
      }
      let previous = -1;
      for (const heading of ['01 赛道理解', '02 赛道问题池', '03 用户语言与评论问题库', '04 赛道传播规律']) {
        const current = segment.indexOf(`#### ${heading}`);
        if (current < 0) failures.push(`SUMMARY_TRACK_HEADING_MISSING ${trackId}:${heading}`);
        if (current >= 0 && current <= previous) failures.push(`SUMMARY_TRACK_ORDER_INVALID ${trackId}:${heading}`);
        previous = current;
      }
      for (const problem of track.track_problem_pool || []) {
        if (!segment.includes(problem.problem)) failures.push(`SUMMARY_PROBLEM_MISSING ${trackId}:${problem.problem_id}`);
      }
      if (track.user_response_map?.status === 'verified') {
        for (const section of track.user_response_map.sections || []) {
          for (const insight of section.insights || []) {
            if (!segment.includes(insight.text)) failures.push(`SUMMARY_USER_INSIGHT_MISSING ${trackId}:${section.type}`);
          }
        }
      }
      for (const pattern of track.track_spread_patterns || []) {
        if (!segment.includes(pattern.text)) failures.push(`SUMMARY_SPREAD_PATTERN_MISSING ${trackId}:${pattern.pattern_id}`);
      }

      const relativePage = data.track_pages?.[trackId];
      if (!valueText(relativePage)) {
        failures.push(`TRACK_PAGE_PATH_MISSING ${trackId}`);
      } else {
        validateTrackPage(path.resolve(path.dirname(summaryPath), relativePage), track);
      }
    }
  }
}

if (data.schema_version === 'track-database-v4.0-generic') validateV4();
else validateLegacy();

if (failures.length) {
  console.error('TRACK_DATABASE_VALIDATION_FAILED');
  console.error(failures.join('\n'));
  process.exit(1);
}

if (data.schema_version === 'track-database-v4.0-generic') {
  console.log(`TRACK_DATABASE_VALIDATION_OK schema=v4 tracks=${Object.keys(data.tracks).length} file=${path.basename(jsonPath)}`);
} else {
  console.log(`TRACK_DATABASE_VALIDATION_OK schema=legacy stable_pools=4 frontstage_sections=4 file=${path.basename(jsonPath)}`);
}

