#!/usr/bin/env node

const fs = require('fs');
const { execFileSync } = require('child_process');

const TRANSCRIPT_HEADING = '## ASR 全文';

function normalizeContent(text) {
  return Array.from(String(text || '').toLowerCase())
    .filter((char) => /[a-z0-9\u3400-\u9fff\u0400-\u04ff]/i.test(char))
    .join('');
}

function ngramUniqueRatio(text, width = 4) {
  if (text.length < width) return 1;
  const grams = [];
  for (let index = 0; index <= text.length - width; index += 1) {
    grams.push(text.slice(index, index + width));
  }
  return new Set(grams).size / grams.length;
}

function duplicateLineRatio(text) {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map(normalizeContent)
    .filter((line) => line.length >= 2);
  if (!lines.length) return 0;
  const counts = new Map();
  for (const line of lines) counts.set(line, (counts.get(line) || 0) + 1);
  let duplicateChars = 0;
  let totalChars = 0;
  for (const [line, count] of counts.entries()) {
    duplicateChars += line.length * Math.max(0, count - 1);
    totalChars += line.length * count;
  }
  return totalChars ? duplicateChars / totalChars : 0;
}

function evaluateTextQuality(text, durationSeconds) {
  const compact = normalizeContent(text);
  const tokens = String(text || '').match(/[A-Za-z0-9_]+|[\u3400-\u9fff]/g) || [];
  const normalizedTokens = tokens.map((token) => token.toLowerCase());
  const counts = new Map();
  for (const token of normalizedTokens) counts.set(token, (counts.get(token) || 0) + 1);
  const dominant = [...counts.entries()].sort((left, right) => right[1] - left[1])[0] || ['', 0];
  const dominantTokenRatio = normalizedTokens.length ? dominant[1] / normalizedTokens.length : 0;
  const tokenUniqueRatio = normalizedTokens.length ? counts.size / normalizedTokens.length : 0;
  const expectedScriptChars = Array.from(compact)
    .filter((char) => /[A-Za-z0-9\u3400-\u9fff]/.test(char)).length;
  const expectedScriptRatio = compact.length ? expectedScriptChars / compact.length : 0;
  const charsPerSecond = durationSeconds > 0 ? compact.length / durationSeconds : 0;
  const metrics = {
    body_chars: compact.length,
    token_count: normalizedTokens.length,
    dominant_token: dominant[0],
    dominant_token_ratio: Number(dominantTokenRatio.toFixed(4)),
    token_unique_ratio: Number(tokenUniqueRatio.toFixed(4)),
    ngram_unique_ratio: Number(ngramUniqueRatio(compact).toFixed(4)),
    duplicate_line_ratio: Number(duplicateLineRatio(text).toFixed(4)),
    chars_per_second: Number(charsPerSecond.toFixed(4)),
    expected_script_ratio: Number(expectedScriptRatio.toFixed(4))
  };
  const failures = [];
  const warnings = [];

  if (compact.length < 50) failures.push('transcript_body_too_short');
  if (normalizedTokens.length >= 20 && dominantTokenRatio >= 0.45) {
    failures.push('dominant_token_repetition');
  }
  if (normalizedTokens.length >= 30 && tokenUniqueRatio < 0.08) {
    failures.push('token_diversity_too_low');
  }
  if (compact.length >= 100 && metrics.ngram_unique_ratio < 0.12) {
    failures.push('ngram_diversity_too_low');
  }
  if (metrics.duplicate_line_ratio >= 0.55) failures.push('duplicate_lines_excessive');
  if (compact.length >= 50 && expectedScriptRatio < 0.6) {
    failures.push('unexpected_script_ratio_high');
  }
  if (durationSeconds >= 30 && charsPerSecond < 0.18) {
    failures.push('transcript_density_too_low');
  } else if (durationSeconds >= 30 && charsPerSecond < 0.45) {
    warnings.push('transcript_density_low_review_needed');
  }
  if (durationSeconds >= 8 && charsPerSecond > 10) {
    failures.push('transcript_density_impossibly_high');
  }

  return {
    status: failures.length ? 'failed' : 'passed',
    failures: [...new Set(failures)].sort(),
    warnings: [...new Set(warnings)].sort(),
    metrics
  };
}

function checkTranscript(mediaFile, asrFile, transcriptFile) {
  const report = {
    qualified: false,
    automatic_quality: 'failed',
    media_file: mediaFile,
    asr_file: asrFile,
    transcript_file: transcriptFile,
    failures: [],
    warnings: []
  };

  for (const [label, file] of [['media', mediaFile], ['asr', asrFile], ['transcript', transcriptFile]]) {
    if (!fs.existsSync(file) || fs.statSync(file).size === 0) {
      report.failures.push(`${label}_missing_or_empty`);
    }
  }

  if (report.failures.length === 0) {
    try {
      report.media_size_bytes = fs.statSync(mediaFile).size;
      const probe = JSON.parse(execFileSync('ffprobe', [
        '-v', 'error', '-show_entries', 'format=duration,format_name,size', '-of', 'json', mediaFile
      ], { encoding: 'utf8' }));
      report.media_duration_seconds = Number(probe?.format?.duration || 0);
      report.media_format = probe?.format?.format_name || '';
      if (!(report.media_duration_seconds > 0)) report.failures.push('media_duration_invalid');
    } catch (error) {
      report.failures.push('ffprobe_failed');
    }

    try {
      const asr = JSON.parse(fs.readFileSync(asrFile, 'utf8'));
      const utterances = asr?.result?.utterances || asr?.utterances || [];
      const valid = utterances.filter((item) => String(item?.text || '').trim());
      report.asr_utterance_count = valid.length;
      report.asr_text_chars = valid.reduce((sum, item) => sum + String(item.text).trim().length, 0);
      if (!valid.length) {
        report.failures.push('asr_has_no_text');
      } else if (report.media_duration_seconds > 0) {
        const starts = valid.map((item) => Number(item.start_time)).filter(Number.isFinite);
        const ends = valid.map((item) => Number(item.end_time)).filter(Number.isFinite);
        report.opening_gap_seconds = starts.length ? Math.min(...starts) / 1000 : null;
        report.ending_gap_seconds = ends.length
          ? Math.max(0, report.media_duration_seconds - Math.max(...ends) / 1000)
          : null;
        const maxGap = Number(process.env.JIANGDAO_MAX_ASR_EDGE_GAP_SECONDS || 10);
        if (report.opening_gap_seconds === null || report.opening_gap_seconds > maxGap) {
          report.failures.push('opening_coverage_insufficient');
        }
        if (report.ending_gap_seconds === null || report.ending_gap_seconds > maxGap) {
          report.failures.push('ending_coverage_insufficient');
        }
      }
    } catch (error) {
      report.failures.push('asr_json_invalid');
    }

    const transcript = fs.readFileSync(transcriptFile, 'utf8');
    const hasHeading = transcript.includes(TRANSCRIPT_HEADING);
    const body = hasHeading ? transcript.split(TRANSCRIPT_HEADING)[1] || '' : '';
    if (!hasHeading) report.failures.push('transcript_body_heading_missing');
    const quality = evaluateTextQuality(body, report.media_duration_seconds || 0);
    report.text_quality = quality;
    report.transcript_body_chars = quality.metrics.body_chars;
    report.failures.push(...quality.failures);
    report.warnings.push(...quality.warnings);
  }

  report.failures = [...new Set(report.failures)].sort();
  report.warnings = [...new Set(report.warnings)].sort();
  report.qualified = report.failures.length === 0;
  report.automatic_quality = report.qualified ? 'passed' : 'failed';
  return report;
}

function main(argv = process.argv.slice(2)) {
  const [mediaFile, asrFile, transcriptFile] = argv;
  if (!mediaFile || !asrFile || !transcriptFile) {
    console.error('用法: check-douyin-transcript.js <MP4> <asr_result.json> <逐字稿.md>');
    return 2;
  }
  const report = checkTranscript(mediaFile, asrFile, transcriptFile);
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  return report.qualified ? 0 : 1;
}

if (require.main === module) process.exit(main());

module.exports = { checkTranscript, evaluateTextQuality, main, normalizeContent };
