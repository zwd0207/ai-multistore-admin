import assert from 'node:assert/strict';
import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';

const distDir = path.resolve('dist');
const assetsDir = path.join(distDir, 'assets');
const html = await readFile(path.join(distDir, 'index.html'), 'utf8');
const entryMatch = html.match(/<script[^>]+src="\.\/assets\/([^"]+\.js)"/);

assert.ok(entryMatch, 'production index must reference a JavaScript entry chunk');

const entryBytes = (await stat(path.join(assetsDir, entryMatch[1]))).size;
assert.ok(entryBytes <= 300 * 1024, `entry chunk exceeds 300 KiB: ${entryBytes} bytes`);

const javascriptFiles = (await readdir(assetsDir)).filter((file) => file.endsWith('.js'));
assert.ok(javascriptFiles.length > 1, 'production build must contain route-level JavaScript chunks');

for (const file of javascriptFiles) {
  const bytes = (await stat(path.join(assetsDir, file))).size;
  assert.ok(bytes <= 500 * 1024, `${file} exceeds 500 KiB: ${bytes} bytes`);
}

console.log(`Bundle budget passed: entry ${entryBytes} bytes, ${javascriptFiles.length} JavaScript chunks.`);
