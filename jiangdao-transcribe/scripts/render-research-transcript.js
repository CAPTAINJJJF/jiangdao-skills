#!/usr/bin/env node

const fs = require('fs');

const [resultFile, metadataFile, outputFile] = process.argv.slice(2);
if (!resultFile || !metadataFile || !outputFile) {
  console.error('用法: render-research-transcript.js <asr_result.json> <metadata.json> <输出.md>');
  process.exit(1);
}

const result = JSON.parse(fs.readFileSync(resultFile, 'utf8'));
const meta = JSON.parse(fs.readFileSync(metadataFile, 'utf8'));
const utterances = result?.result?.utterances || result?.utterances || [];
const texts = utterances.map((item) => String(item.text || '').trim()).filter(Boolean);

if (!texts.length) {
  console.error('ASR 结果没有可用 utterance');
  process.exit(2);
}

const paragraphs = [];
let current = '';
for (const text of texts) {
  current += text;
  if (current.length >= 320 || /[。！？?!]$/.test(text) && current.length >= 220) {
    paragraphs.push(current);
    current = '';
  }
}
if (current) paragraphs.push(current);

const title = meta.title || meta.id;
const pendingTerms = meta.pending_terms || '未做人工逐字听校；专名和同音词按 ASR 原始结果保留';
const lines = [
  `# ${meta.id}｜《${title}》内部逐字稿`,
  '',
  `- 来源：${meta.author}，${meta.platform || '抖音'}，${meta.published_at}`,
  `- 原始链接：${meta.source_url}`,
  `- 转写状态：成功；本机 MLX Whisper；${utterances.length} 个识别段；未做人工逐字听校`,
  '- 用途：第三方公开内容的内部研究证据，不对外替代原作',
  `- 待核实词：${pendingTerms}`,
  '',
  '## ASR 全文',
  '',
  paragraphs.join('\n\n'),
  ''
];

fs.mkdirSync(require('path').dirname(outputFile), { recursive: true });
fs.writeFileSync(outputFile, lines.join('\n'));
