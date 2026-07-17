import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

const authPages = read('src/pages/AuthPages.jsx');
const tenantPages = read('src/pages/TenantPages.jsx');
const backendApi = read('src/services/backendApi.js');
const globalCss = read('src/styles/global.css');

assert.match(backendApi, /safeErrorMessage/);
assert.match(backendApi, /safeSendData/);
assert.match(backendApi, /createTenantInvitation:[\s\S]*safeSendData/);
assert.match(backendApi, /getTenants:[\s\S]*safeGetData/);
assert.doesNotMatch(authPages, /requestError\.message|nextError\.message/);
assert.doesNotMatch(tenantPages, /requestError\.message/);
assert.doesNotMatch(authPages, /mfa_secret/);
assert.match(authPages, /function useSensitiveHashParam\(name\)[\s\S]*stripSensitiveHashParam\(name\)/);
assert.match(authPages, /AcceptInvitationPage\(\)[\s\S]*useSensitiveHashParam\('token'\)/);
assert.match(authPages, /PasswordResetPage\([\s\S]*useSensitiveHashParam\('token'\)/);
assert.match(authPages, /normalizeRecoveryCodes/);
assert.match(authPages, /isSafeOtpAuthUri/);
assert.match(authPages, /recovery_codes/);
assert.match(tenantPages, /useTenantDirectory\(isPlatformAdmin\)/);
assert.match(tenantPages, /useMobileReadOnly/);
assert.match(tenantPages, /data-mobile-readonly/);
assert.match(tenantPages, /mobile-readonly-notice/);
assert.match(tenantPages, /if \(isMobileReadOnly\)/);
assert.match(globalCss, /\.mobile-readonly-notice/);
assert.match(globalCss, /\.auth-security-note/);
assert.match(backendApi, /account_already_exists: '该邮箱已经注册。'/);
assert.match(backendApi, /safeErrorMessage\(error, fallback\)/);
assert.doesNotMatch(backendApi, /safe\.message\s*=\s*error\.message/);
assert.doesNotMatch(backendApi, /response\?\.message/);

console.log('T23/T26 auth safety and mobile boundary contract passed');
