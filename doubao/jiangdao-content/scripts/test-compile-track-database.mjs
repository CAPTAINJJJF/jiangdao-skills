#!/usr/bin/env node

import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const compiler = path.join(scriptDir, 'compile-track-database.mjs');
const validator = path.join(scriptDir, 'validate-track-database-v2.mjs');

function baseManifest(root) {
  for (const id of ['S1', 'S2', 'S3', 'S4']) {
    fs.writeFileSync(path.join(root, `${id}.md`), `# ${id}\n完整详情\n`);
  }
  for (const id of ['Q1', 'Q2', 'Q3']) {
    fs.writeFileSync(path.join(root, `${id}.md`), `# ${id}\n真实评论证据\n`);
  }

  return {
    schema_version: 'track-database-compilation-v1',
    evidence_root: '.',
    core_track_keywords: ['青春期亲子沟通'],
    source_records: [
      { record_id: 'S1', title: '孩子关门以后怎么沟通', detail_path: 'S1.md', input_state: 'full_text' },
      { record_id: 'S2', title: '冲突升级前家长能做什么', detail_path: 'S2.md', input_state: 'full_text' },
      { record_id: 'S3', title: '小学阅读时间怎么分配', detail_path: 'S3.md', input_state: 'full_text' },
      { record_id: 'S4', title: '普通家庭怎样选课外学习', detail_path: 'S4.md', input_state: 'full_text' },
    ],
    source_problems: [
      { source_problem_id: 'SP1', question: '孩子拒绝沟通时，家长怎样重新建立对话？', record_id: 'S1', track_ids: ['parent'], evidence_identity: '作者全文还原' },
      { source_problem_id: 'SP2', question: '亲子冲突升级前，家长怎样让对话继续？', record_id: 'S2', track_ids: ['parent'], evidence_identity: '作者全文还原' },
      { source_problem_id: 'SP3', question: '小学阶段有限的课外时间应该怎样分配？', record_id: 'S3', track_ids: ['k12'], evidence_identity: '作者全文还原' },
      { source_problem_id: 'SP4', question: '普通家庭怎样判断哪些课外学习真正值得投入？', record_id: 'S4', track_ids: ['k12'], evidence_identity: '作者全文还原' },
    ],
    answer_assets: [
      { answer_id: 'AN1', record_id: 'S1', track_ids: ['parent'], text: '先降低追问密度，再用具体事件恢复对话。' },
      { answer_id: 'AN2', record_id: 'S2', track_ids: ['parent'], text: '先识别冲突触发点，再调整家长回应顺序。' },
      { answer_id: 'AN3', record_id: 'S3', track_ids: ['k12'], text: '围绕阅读、习惯和长期能力安排课外时间。' },
      { answer_id: 'AN4', record_id: 'S4', track_ids: ['k12'], text: '按家庭目标、孩子阶段和投入回报筛选。' },
    ],
    comment_quotes: [
      { quote_id: 'Q1', record_id: 'S1', track_ids: ['parent'], quote: '原来一直追问真的会让孩子更想躲。', response_type: '用户容易认可什么', evidence_path: 'Q1.md', evidence_status: 'real_user_quote' },
      { quote_id: 'Q2', record_id: 'S1', track_ids: ['parent'], quote: '孩子已经不说话了，第一句到底怎么开口？', response_type: '用户会继续追问什么', evidence_path: 'Q2.md', evidence_status: 'real_user_quote' },
      { quote_id: 'Q3', record_id: 'S2', track_ids: ['parent'], quote: '只让家长改变，会不会忽略孩子也有责任？', response_type: '用户会质疑或反对什么', evidence_path: 'Q3.md', evidence_status: 'real_user_quote' },
    ],
    topic_processing_actions: [
      { action_id: 'A1', record_id: 'S1', track_ids: ['parent'], action: '选题具体化', evidence_quote: '把沟通问题落到孩子关门的场景。' },
      { action_id: 'A2', record_id: 'S3', track_ids: ['k12'], action: '收益显化', evidence_quote: '帮助家长完成时间分配。' },
    ],
    spread_signals: [
      { signal_id: 'SS1', record_id: 'S1', track_ids: ['parent'], text: '具体冲突现场更容易让家长代入。', evidence_basis: '正文与评论共同支持，缺点击数据。' },
      { signal_id: 'SS2', record_id: 'S2', track_ids: ['parent'], text: '回应顺序能提供可执行价值。', evidence_basis: '两条同赛道内容反复出现，缺同账号对照。' },
      { signal_id: 'SS3', record_id: 'S3', track_ids: ['k12'], text: '帮助家庭做选择的内容有收藏价值。', evidence_basis: '正文提供清晰选择框架。' },
      { signal_id: 'SS4', record_id: 'S4', track_ids: ['k12'], text: '投入取舍能触发家长关注。', evidence_basis: '两条内容均围绕资源分配，缺评论证据。' },
    ],
    tracks: [
      {
        track_id: 'parent',
        display_name: '青春期亲子沟通',
        role: 'core',
        confirmed_keyword: '青春期亲子沟通',
        source_record_ids: ['S1', 'S2'],
        understanding: {
          paragraphs: [
            { text: '青春期亲子沟通长期聚焦冲突怎样发生、家长怎样回应，以及关系紧张后怎样恢复对话。家长最关心的是具体场景里第一步做什么，避免一句话让冲突继续升级。', aspects: ['industry_focus', 'user_interest'], evidence_ids: ['SP1', 'SP2', 'Q2'] },
            { text: '常见服务围绕家长课程、咨询和训练营展开，长期缺口在于把通用话术推进到不同冲突类型、家庭边界和适用条件，让家长知道方法什么时候有效。', aspects: ['monetization', 'long_term_gap'], evidence_ids: ['AN1', 'AN2', 'Q3'] },
          ],
        },
        problem_groups: [
          { problem_id: 'P1', question: '亲子冲突中，家长怎样调整回应，让对话能够继续？', source_problem_ids: ['SP1', 'SP2'], merge_audit: { shared_core_need: '恢复对话并降低冲突升级', differences_change_answer: false, reason: '两条问题都发生在冲突沟通阶段，回答都需要调整家长回应顺序。' } },
        ],
        excluded_source_problems: [],
        user_response_map: {
          status: 'verified',
          sections: [
            { type: '用户容易认可什么', insights: [{ text: '家长容易认可能解释孩子为什么越问越躲的具体冲突机制。', quote_ids: ['Q1'] }] },
            { type: '用户会继续追问什么', insights: [{ text: '理解原因以后，用户会继续追问第一句话和第一步动作。', quote_ids: ['Q2'] }] },
            { type: '用户会质疑或反对什么', insights: [{ text: '只强调家长责任时，用户会担心内容忽略孩子和家庭双方的边界。', quote_ids: ['Q3'] }] },
            { type: '这些反应说明什么', insights: [{ text: '用户既需要可执行方法，也会检查责任边界和方法是否适合自己的家庭。', quote_ids: ['Q1', 'Q2', 'Q3'] }] },
          ],
        },
        spread_patterns: [
          { pattern_id: 'R1', text: '把抽象沟通原则放进一个真实冲突现场，更容易产生代入和继续追问。', signal_ids: ['SS1', 'SS2'], scope: '当前两条青春期亲子沟通文本样本', evidence_boundary: '缺点击、完播和同账号对照。' },
        ],
        topic_processing_library: [
          { library_id: 'TA1', action: '选题具体化', source_action_ids: ['A1'], applicable_condition: '抽象沟通问题能落到真实冲突现场时', boundary: '场景会改变问题核心时需要重新建题' },
        ],
        aggregation_gaps: {},
      },
      {
        track_id: 'k12',
        display_name: '家庭教育与学业规划',
        role: 'business_contact',
        source_record_ids: ['S3', 'S4'],
        understanding: {
          paragraphs: [
            { text: '家庭教育与学业规划反复讨论时间、金钱和孩子精力怎样分配。家长最关注不同阶段该做什么，以及哪些投入看起来努力却没有长期价值。', aspects: ['industry_focus', 'user_interest'], evidence_ids: ['SP3', 'SP4'] },
            { text: '课程、规划和家长咨询通常围绕这些选择形成服务，长期缺口是把统一建议推进到家庭条件、孩子基础和阶段差异，减少机械套用。', aspects: ['monetization', 'long_term_gap'], evidence_ids: ['AN3', 'AN4'] },
          ],
        },
        problem_groups: [
          { problem_id: 'KP1', question: '普通家庭怎样分配课外时间和投入，才能做出适合孩子阶段的选择？', source_problem_ids: ['SP3', 'SP4'], merge_audit: { shared_core_need: '在有限资源下判断课外投入', differences_change_answer: false, reason: '两条问题都需要结合家庭条件和孩子阶段完成资源选择。' } },
        ],
        excluded_source_problems: [],
        user_response_map: { status: 'unavailable', reason: '当前两条样本没有取得真实评论原话。', sections: [] },
        spread_patterns: [
          { pattern_id: 'KR1', text: '直接帮助家长完成投入取舍的内容，更容易形成明确的决策价值。', signal_ids: ['SS3', 'SS4'], scope: '当前两条家庭教育文本样本', evidence_boundary: '缺评论、点击和收藏明细。' },
        ],
        topic_processing_library: [
          { library_id: 'KTA1', action: '收益显化', source_action_ids: ['A2'], applicable_condition: '内容确实能够帮助家庭完成选择时', boundary: '无法交付具体判断标准时不显化收益' },
        ],
        aggregation_gaps: { comments: '缺真实评论原话' },
      },
    ],
  };
}

function runCompiler(manifest, root, extraArgs = ['--check']) {
  const manifestPath = path.join(root, 'manifest.json');
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  return spawnSync(process.execPath, [compiler, '--manifest', manifestPath, ...extraArgs], { encoding: 'utf8' });
}

function expectFailure(name, mutate, code) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'track-db-fail-'));
  try {
    const manifest = baseManifest(root);
    mutate(manifest);
    const result = runCompiler(manifest, root);
    assert.notEqual(result.status, 0, `${name} should fail`);
    assert.match(`${result.stdout}\n${result.stderr}`, new RegExp(code), `${name} should report ${code}`);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

let passed = 0;
const validRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'track-db-valid-'));
try {
  const manifest = baseManifest(validRoot);
  const out = path.join(validRoot, 'out');
  const result = runCompiler(manifest, validRoot, ['--out', out]);
  assert.equal(result.status, 0, result.stderr);
  const validation = spawnSync(process.execPath, [
    validator,
    path.join(out, '赛道数据库', '赛道汇总库.json'),
    path.join(out, '赛道数据库.md'),
  ], { encoding: 'utf8' });
  assert.equal(validation.status, 0, validation.stderr);
  const page = fs.readFileSync(path.join(out, '赛道数据库.md'), 'utf8');
  assert.match(page, /核心赛道词：青春期亲子沟通/);
  assert.ok(page.indexOf('### 青春期亲子沟通') < page.indexOf('### 家庭教育与学业规划'));
  assert.doesNotMatch(page, /高价值选题池|当前内容机会|P1|SP1|样本数|证据状态/);
  const demoOut = process.env.TRACK_DB_DEMO_OUT;
  if (demoOut) {
    const resolvedDemo = path.resolve(demoOut);
    if (fs.existsSync(resolvedDemo) && fs.readdirSync(resolvedDemo).length) {
      throw new Error(`demo output is not empty: ${resolvedDemo}`);
    }
    fs.mkdirSync(resolvedDemo, { recursive: true });
    for (const name of fs.readdirSync(validRoot).filter((name) => name !== 'out')) {
      fs.cpSync(path.join(validRoot, name), path.join(resolvedDemo, name), { recursive: true });
    }
    fs.cpSync(out, path.join(resolvedDemo, '修复后'), { recursive: true });
  }
  passed += 1;
} finally {
  fs.rmSync(validRoot, { recursive: true, force: true });
}

expectFailure('business track mixing', (manifest) => {
  manifest.tracks[1].confirmed_keyword = '青春期亲子沟通';
}, 'BUSINESS_TRACK_MIXED_IN_CORE');
passed += 1;

expectFailure('unassigned source problem', (manifest) => {
  manifest.tracks[0].problem_groups[0].source_problem_ids = ['SP1'];
}, 'SOURCE_PROBLEM_UNASSIGNED');
passed += 1;

expectFailure('fake comment evidence', (manifest) => {
  manifest.comment_quotes[0].evidence_status = 'ai_summary';
}, 'COMMENT_QUOTE_NOT_REAL');
passed += 1;

expectFailure('single sample spread pattern', (manifest) => {
  manifest.tracks[0].spread_patterns[0].signal_ids = ['SS1'];
}, 'SPREAD_PATTERN_NOT_CROSS_SAMPLE');
passed += 1;

console.log(`TRACK_DATABASE_COMPILER_TESTS_OK ${passed}/5`);
