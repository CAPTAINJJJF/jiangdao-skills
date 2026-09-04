#!/usr/bin/env node
/**
 * Adapted from chengfeng-videocut-skills under Apache-2.0.
 * Modified 2026-08-12 by 江导项目: loopback-only server, safe path handling,
 * validated deletion ranges, argument-safe process calls, and local script names.
 *
 * Usage: node review-server.js [port] [video_file]
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const HOST = '127.0.0.1';
const PORT = Number(process.argv[2] || 8899);
const ROOT = path.resolve(process.cwd());
const VIDEO_FILE = path.resolve(process.argv[3] || findVideoFile());
const CUT_SCRIPT = path.join(__dirname, 'cut-approved-segments.sh');
const MAX_BODY_BYTES = 1024 * 1024;

function findVideoFile() {
  const file = fs.readdirSync(ROOT).find(name => /\.(mp4|mov|m4v)$/i.test(name));
  return file || 'video.mp4';
}

function sendJson(res, status, value) {
  const body = JSON.stringify(value);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', chunk => {
      body += chunk;
      if (Buffer.byteLength(body) > MAX_BODY_BYTES) {
        reject(new Error('请求内容超过 1MB'));
        req.destroy();
      }
    });
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

function normalizeDeleteList(value) {
  if (!Array.isArray(value)) throw new Error('删除列表必须是数组');
  const normalized = value.map((item, index) => {
    const start = Number(item?.start);
    const end = Number(item?.end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) {
      throw new Error(`第 ${index + 1} 个删除区间无效`);
    }
    return { start, end };
  });
  return normalized.sort((a, b) => a.start - b.start);
}

function probeDuration(file) {
  return Number(execFileSync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', `file:${file}`
  ], { encoding: 'utf8' }).trim());
}

function safeStaticPath(url) {
  const pathname = decodeURIComponent(String(url || '/').split('?')[0]);
  const relative = pathname === '/' ? 'review.html' : pathname.replace(/^\/+/, '');
  const resolved = path.resolve(ROOT, relative);
  if (resolved !== ROOT && !resolved.startsWith(`${ROOT}${path.sep}`)) return null;
  return resolved;
}

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.mp3': 'audio/mpeg',
  '.mp4': 'video/mp4',
  '.mov': 'video/quicktime'
};

async function handleRequest(req, res) {
  if (req.method === 'POST' && req.url === '/api/save-selection') {
    const body = await readBody(req);
    JSON.parse(body);
    fs.writeFileSync(path.join(ROOT, 'saved_selection.json'), body);
    return sendJson(res, 200, { success: true });
  }

  if (req.method === 'GET' && req.url === '/api/load-selection') {
    const file = path.join(ROOT, 'saved_selection.json');
    if (!fs.existsSync(file)) return sendJson(res, 404, { error: 'no saved selection' });
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    return res.end(fs.readFileSync(file));
  }

  if (req.method === 'POST' && req.url === '/api/cut') {
    if (!fs.existsSync(VIDEO_FILE)) throw new Error(`找不到视频: ${VIDEO_FILE}`);
    if (!fs.existsSync(CUT_SCRIPT)) throw new Error(`找不到剪辑脚本: ${CUT_SCRIPT}`);

    const deleteList = normalizeDeleteList(JSON.parse(await readBody(req)));
    const deleteFile = path.join(ROOT, 'delete_segments.json');
    fs.writeFileSync(deleteFile, JSON.stringify(deleteList, null, 2));

    const parsed = path.parse(VIDEO_FILE);
    const outputFile = path.join(ROOT, `${parsed.name}_cut.mp4`);
    execFileSync('bash', [CUT_SCRIPT, VIDEO_FILE, deleteFile, outputFile], { stdio: 'inherit' });

    const originalDuration = probeDuration(VIDEO_FILE);
    const newDuration = probeDuration(outputFile);
    const deletedDuration = Math.max(0, originalDuration - newDuration);
    const cutDone = {
      success: true,
      output: outputFile,
      originalDuration: originalDuration.toFixed(2),
      newDuration: newDuration.toFixed(2),
      deletedDuration: deletedDuration.toFixed(2),
      savedPercent: originalDuration > 0 ? ((deletedDuration / originalDuration) * 100).toFixed(1) : '0.0',
      completedAt: new Date().toISOString(),
      nextStep: '从剪后视频重新转写，校对后生成同版本 subtitles.srt。'
    };
    fs.writeFileSync(path.join(ROOT, 'cut_done.json'), JSON.stringify(cutDone, null, 2));
    return sendJson(res, 200, cutDone);
  }

  if (req.method !== 'GET') return sendJson(res, 405, { error: 'method not allowed' });

  const filePath = safeStaticPath(req.url);
  if (!filePath) return sendJson(res, 403, { error: 'forbidden path' });
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    res.writeHead(404);
    return res.end('Not Found');
  }

  const stat = fs.statSync(filePath);
  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';
  const rangeHeader = req.headers.range;

  if (rangeHeader && /\.(mp3|mp4|mov)$/i.test(filePath)) {
    const match = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader);
    if (!match) {
      res.writeHead(416, { 'Content-Range': `bytes */${stat.size}` });
      return res.end();
    }
    const start = match[1] ? Number(match[1]) : 0;
    const end = match[2] ? Math.min(Number(match[2]), stat.size - 1) : stat.size - 1;
    if (start > end || start >= stat.size) {
      res.writeHead(416, { 'Content-Range': `bytes */${stat.size}` });
      return res.end();
    }
    res.writeHead(206, {
      'Content-Type': contentType,
      'Content-Range': `bytes ${start}-${end}/${stat.size}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': end - start + 1
    });
    return fs.createReadStream(filePath, { start, end }).pipe(res);
  }

  res.writeHead(200, {
    'Content-Type': contentType,
    'Content-Length': stat.size,
    'Accept-Ranges': 'bytes'
  });
  fs.createReadStream(filePath).pipe(res);
}

const server = http.createServer((req, res) => {
  handleRequest(req, res).catch(error => {
    console.error('❌ 请求失败:', error.message);
    if (!res.headersSent) sendJson(res, 500, { success: false, error: error.message });
    else res.end();
  });
});

server.listen(PORT, HOST, () => {
  console.log(`🎬 江导本机审核服务已启动\n📍 http://${HOST}:${PORT}/review.html\n📹 ${VIDEO_FILE}`);
});
