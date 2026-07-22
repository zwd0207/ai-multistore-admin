import assert from 'node:assert/strict';
import fs from 'node:fs';

const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
const runner = fs.readFileSync('scripts/verify-completed-capabilities.mjs', 'utf8');
const baseline = fs.readFileSync('docs/COMPLETED_CAPABILITY_BASELINE.md', 'utf8');
const roadmap = fs.readFileSync('docs/DEVELOPMENT_ROADMAP.md', 'utf8');
const control = fs.readFileSync('docs/PROJECT_CONTROL.md', 'utf8');

assert.equal(
  packageJson.scripts['capabilities:verify'],
  'node scripts/verify-completed-capabilities.mjs',
);
assert.equal(
  packageJson.scripts['capabilities:verify:full'],
  'node scripts/verify-completed-capabilities.mjs --full',
);
assert.match(runner, /endsWith\('\.test\.mjs'\)/);
assert.match(runner, /verify_all\.py/);
assert.match(baseline, /唯一主实现/);
assert.match(baseline, /A2 表示技术链路已验证/);
assert.match(roadmap, /工作流一：核心数据合同/);
assert.match(roadmap, /工作流二：内部运营闭环/);
assert.match(control, /COMPLETED_CAPABILITY_BASELINE\.md/);
assert.match(control, /DEVELOPMENT_ROADMAP\.md/);

console.log('completed capability baseline contract passed');
