import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const versionPath = path.join(process.cwd(), 'public', 'release-version.json');
const release = JSON.parse(fs.readFileSync(versionPath, 'utf8'));

assert.equal(release.schema_version, 1);
assert.match(release.release_version, /^operator-v1\.\d{8}\.\d+$/);
assert.equal(release.release_channel, 'release/operator-v1');
assert.match(release.registered_on, /^\d{4}-\d{2}-\d{2}$/);

console.log(`release version contract passed: ${release.release_version}`);
