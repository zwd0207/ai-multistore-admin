import assert from 'node:assert/strict';
import fs from 'node:fs';

const globalCss = fs.readFileSync(new URL('../src/styles/global.css', import.meta.url), 'utf8');
const layoutCss = fs.readFileSync(new URL('../src/styles/layout.css', import.meta.url), 'utf8');
assert.match(globalCss, /\.search-panel\s*\{[^}]*display:\s*grid/);
assert.match(globalCss, /\.modal-card\s*\{[^}]*width:\s*calc\(100vw/);
assert.match(globalCss, /\.detail-grid\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/);
assert.match(layoutCss, /\.topbar-actions\s*\{\s*flex-wrap:\s*wrap/);
assert.match(layoutCss, /\.main-content\s*\{[^}]*overflow-x:\s*hidden/);
console.log('customer inquiry mobile contract checks passed');
