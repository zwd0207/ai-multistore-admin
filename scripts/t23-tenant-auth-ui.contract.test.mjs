import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

const authPages = read('src/pages/AuthPages.jsx');
const authContext = read('src/context/AuthContext.jsx');
const routes = read('src/routes/index.jsx');
const tenantPages = read('src/pages/TenantPages.jsx');
const tenantSelector = read('src/components/common/TenantScopeSelector.jsx');
const backendApi = read('src/services/backendApi.js');
const globalCss = read('src/styles/global.css');

assert.match(authPages, /import\('qrcode'\)[\s\S]*QRCode\.toDataURL/);
assert.match(authPages, /recovery_codes/);
assert.match(authPages, /acceptTenantInvitation/);
assert.match(authPages, /completeMfaEnrollment/);
assert.match(authPages, /requestPasswordReset/);
assert.match(authPages, /completePasswordReset/);
assert.match(authContext, /selectedTenantId/);
assert.match(authContext, /selectTenant/);
assert.match(routes, /path="accept-invite"/);
assert.match(routes, /path="forgot-password"/);
assert.match(routes, /path="reset-password"/);
assert.match(routes, /path="select-tenant"/);
assert.match(routes, /!stores\.length.*\['\/stores', '\/tenants'\]/s);
assert.match(tenantPages, /createTenantInvitation/);
assert.match(tenantPages, /每位受邀用户会获得独立租户/);
assert.match(tenantSelector, /getTenants/);
assert.match(tenantSelector, /selectTenant/);
assert.match(backendApi, /\/admin\/tenants\/\$\{encodeURIComponent\(tenantId\)\}\/select/);
assert.match(globalCss, /\.mfa-qr-code/);
assert.match(globalCss, /\.tenant-invite-form/);
assert.match(globalCss, /@media \(max-width: 600px\)[\s\S]*\.tenant-invite-form \{ grid-template-columns: minmax\(0, 1fr\); \}/);
assert.doesNotMatch(globalCss, /letter-spacing:\s*-/);

console.log('T23 tenant authentication UI contract passed');
