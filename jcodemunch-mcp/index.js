#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname);
const WORKSPACE = path.resolve(ROOT, '..');
const CAPTURE_EXTS = ['.py', '.js', '.ts'];

function listFiles(base) {
  const files = [];
  const stack = [base];
  while (stack.length) {
    const current = stack.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const entryPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === 'node_modules' || entry.name === '.git') continue;
        stack.push(entryPath);
        continue;
      }
      files.push(entryPath);
    }
  }
  return files;
}

function munchFile(location) {
  const text = fs.readFileSync(location, 'utf-8');
  const cleaned = text
    .split('\n')
    .map((line) => line.replace(/[ \t]+$/u, ''))
    .filter((line) => line.trim().length > 0 || line === '')
    .join('\n');
  fs.writeFileSync(location, cleaned + (cleaned.endsWith('\n') ? '' : '\n'));
  return { path: location, length: cleaned.length };
}

function munch(limit = 20) {
  const workFiles = listFiles(WORKSPACE).filter((file) => CAPTURE_EXTS.includes(path.extname(file)));
  return workFiles.slice(0, limit).map((file) => {
    const before = fs.readFileSync(file, 'utf-8').length;
    const result = munchFile(file);
    const after = fs.readFileSync(file, 'utf-8').length;
    return { file: path.relative(WORKSPACE, result.path), before, after, newLength: result.length };
  });
}

function handleRequest(payload) {
  if (!payload || typeof payload.method !== 'string') {
    return { status: 'invalid request' };
  }
  if (payload.method === 'list_tools') {
    return {
      tools: [
        {
          name: 'munch',
          description: 'Membuat file script Python/JS/TS lebih rapih dengan trim trailing whitespace.',
          inputSchema: {
            type: 'object',
            properties: {
              limit: { type: 'integer', minimum: 1, maximum: 50 },
            },
          },
        },
      ],
    };
  }
  if (payload.method === 'munch') {
    const limit = Math.min(Math.max(1, Number(payload.params?.limit || 10)), 50);
    return { status: 'ok', report: munch(limit) };
  }
  return { status: 'unknown method' };
}

function respond(result) {
  process.stdout.write(JSON.stringify({ result }) + '\n');
}

if (require.main === module) {
  let buffer = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => {
    buffer += chunk;
    let idx;
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 1);
      if (!line.trim()) continue;
      try {
        const payload = JSON.parse(line);
        respond(handleRequest(payload));
      } catch (err) {
        respond({ error: err.message });
      }
    }
  });
  process.stdin.on('end', () => {
    if (buffer.trim()) {
      try {
        const payload = JSON.parse(buffer);
        respond(handleRequest(payload));
      } catch (err) {
        respond({ error: err.message });
      }
    }
  });
}

module.exports = {
  handleRequest,
};
