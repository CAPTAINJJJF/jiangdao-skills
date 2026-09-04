#!/usr/bin/env node

const assert = require('assert');
const test = require('node:test');
const { evaluateTextQuality } = require('./check-douyin-transcript.js');

test('rejects repeated Button transcript', () => {
  const report = evaluateTextQuality('Button\n'.repeat(300), 13.4);
  assert.equal(report.status, 'failed');
  assert(report.failures.includes('dominant_token_repetition'));
  assert(report.failures.includes('token_diversity_too_low'));
});

test('rejects foreign-script ASR hallucination', () => {
  const report = evaluateTextQuality('олж'.repeat(220), 13.4);
  assert.equal(report.status, 'failed');
  assert(report.failures.includes('unexpected_script_ratio_high'));
  assert(report.failures.includes('transcript_density_impossibly_high'));
});

test('allows coherent spoken Chinese through automatic checks', () => {
  const text = (
    '孩子背得很熟，为什么换一句问法就不会解释？家长先别急着把答案讲完。' +
    '可以让孩子圈出关键字，再说这个字让他看见了什么画面。' +
    '接着追问人物做了什么，哪一句诗能够证明。这样练习几次，' +
    '孩子会慢慢学会从文字中寻找证据，也能说清自己的理解过程。'
  ).repeat(3);
  const report = evaluateTextQuality(text, 90);
  assert.equal(report.status, 'passed');
  assert.deepEqual(report.failures, []);
});
