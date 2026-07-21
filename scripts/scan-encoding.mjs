import { readFile } from 'node:fs/promises';
import { relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readdirSync, statSync } from 'node:fs';
import path from 'node:path';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const textSuffixes = new Set(['.css', '.html', '.js', '.json', '.jsx', '.md', '.txt']);
const textNames = new Set(['.editorconfig', '.env', '.env.local', '.env.example', '.gitignore']);
const skipDirs = new Set(['.git', 'backend', 'dist', 'node_modules']);
const mojibakeMarkers = new Map([
  ['U+FFFD replacement char', '\uFFFD'],
  ['Chinese mojibake marker', '\u951F\u65A4\u62F7'],
  ['Latin-1 mojibake marker', '\u00C2'],
  ['UTF-8 quote mojibake marker', '\u00E2\u20AC'],
  ['Korean mojibake marker i-grave', '\u00EC'],
  ['Korean mojibake marker e-diaeresis', '\u00EB'],
]);

function shouldScan(filePath) {
  const baseName = path.basename(filePath);
  return textNames.has(baseName) || textSuffixes.has(path.extname(filePath).toLowerCase());
}

function walk(dir) {
  const results = [];
  for (const entry of readdirSync(dir)) {
    if (skipDirs.has(entry)) continue;
    const fullPath = path.join(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      results.push(...walk(fullPath));
    } else if (stats.isFile() && shouldScan(fullPath) && fullPath !== fileURLToPath(import.meta.url)) {
      results.push(fullPath);
    }
  }
  return results.sort();
}

function lineNumberFromBytes(buffer, offset) {
  let lineNumber = 1;
  for (let index = 0; index < offset; index += 1) {
    if (buffer[index] === 10) lineNumber += 1;
  }
  return lineNumber;
}

function firstInvalidUtf8Offset(buffer) {
  let index = 0;
  while (index < buffer.length) {
    const byte = buffer[index];
    if (byte <= 0x7f) {
      index += 1;
    } else if (byte >= 0xc2 && byte <= 0xdf) {
      if (index + 1 >= buffer.length || (buffer[index + 1] & 0xc0) !== 0x80) return index;
      index += 2;
    } else if (byte >= 0xe0 && byte <= 0xef) {
      const next1 = buffer[index + 1];
      const next2 = buffer[index + 2];
      if (index + 2 >= buffer.length || (next1 & 0xc0) !== 0x80 || (next2 & 0xc0) !== 0x80) return index;
      if (byte === 0xe0 && next1 < 0xa0) return index;
      if (byte === 0xed && next1 >= 0xa0) return index;
      index += 3;
    } else if (byte >= 0xf0 && byte <= 0xf4) {
      const next1 = buffer[index + 1];
      const next2 = buffer[index + 2];
      const next3 = buffer[index + 3];
      if (
        index + 3 >= buffer.length
        || (next1 & 0xc0) !== 0x80
        || (next2 & 0xc0) !== 0x80
        || (next3 & 0xc0) !== 0x80
      ) return index;
      if (byte === 0xf0 && next1 < 0x90) return index;
      if (byte === 0xf4 && next1 > 0x8f) return index;
      index += 4;
    } else {
      return index;
    }
  }
  return -1;
}

async function scanFile(filePath) {
  const issues = [];
  const buffer = await readFile(filePath);
  const invalidOffset = firstInvalidUtf8Offset(buffer);
  if (invalidOffset !== -1) {
    issues.push(`${relative(projectRoot, filePath)}:${lineNumberFromBytes(buffer, invalidOffset)}: invalid UTF-8`);
    return issues;
  }
  const text = buffer.toString('utf8');

  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    for (const [label, marker] of mojibakeMarkers) {
      if (line.includes(marker)) {
        issues.push(`${relative(projectRoot, filePath)}:${index + 1}: ${label}: ${line.trim()}`);
      }
    }
  });
  return issues;
}

const issues = [];
for (const filePath of walk(projectRoot)) {
  issues.push(...await scanFile(filePath));
}

if (issues.length > 0) {
  console.error('Encoding scan failed:');
  for (const issue of issues) console.error(issue);
  process.exit(1);
}

console.log('Encoding scan passed: no invalid UTF-8 or mojibake markers found.');
