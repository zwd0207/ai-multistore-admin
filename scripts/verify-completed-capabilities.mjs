import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const backend = path.join(root, 'backend');
const full = process.argv.includes('--full');
const npmCli = [
  process.env.npm_execpath,
  path.join(path.dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js'),
].find((candidate) => candidate && fs.existsSync(candidate));

function run(command, args, cwd = root) {
  const printable = [command, ...args].join(' ');
  console.log(`\n> ${printable}`);
  const result = spawnSync(command, args, {
    cwd,
    stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    throw new Error(`Capability baseline verification failed: ${printable}`);
  }
}

function runNpm(args) {
  if (npmCli) {
    run(process.execPath, [npmCli, ...args]);
    return;
  }
  run('npm', args);
}

const contractTests = fs.readdirSync(path.join(root, 'scripts'))
  .filter((name) => name.endsWith('.test.mjs'))
  .sort();

runNpm(['run', 'encoding:scan']);
runNpm(['run', 'session:verify']);
for (const test of contractTests) {
  run(process.execPath, [path.join('scripts', test)]);
}
runNpm(['run', 'build']);
runNpm(['run', 'bundle:verify']);

if (full) {
  const localPython = process.platform === 'win32'
    ? path.join(backend, '.venv', 'Scripts', 'python.exe')
    : path.join(backend, '.venv', 'bin', 'python');
  const python = fs.existsSync(localPython) ? localPython : (process.env.PYTHON || 'python');
  run(python, [path.join('scripts', 'verify_all.py')], backend);
}

console.log(`\nCompleted capability baseline: ok (${full ? 'frontend + backend' : 'frontend'})`);
