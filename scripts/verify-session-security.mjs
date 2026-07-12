import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [http, authContext, backendApi, storeContext] = await Promise.all([
  readFile(new URL('../src/services/http.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/context/AuthContext.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/services/backendApi.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/context/StoreContext.jsx', import.meta.url), 'utf8'),
]);
const authPage = await readFile(new URL('../src/pages/AuthPages.jsx', import.meta.url), 'utf8');

assert.match(http, /credentials:\s*'include'/, 'all API calls must include HttpOnly cookies');
assert.doesNotMatch(http, /localStorage\.getItem\(['"]access_token['"]\)/, 'session token must not use localStorage');
assert.doesNotMatch(http, /Authorization:\s*`Bearer/, 'frontend must not send Bearer session authorization');
assert.match(http, /X-CSRF-Token/, 'unsafe requests must include the CSRF header');
assert.match(http, /UNSAFE_METHODS/, 'unsafe HTTP methods must be enumerated');
assert.doesNotMatch(authContext, /localStorage|sessionStorage|indexedDB/i, 'AuthContext must not persist session or CSRF data');
assert.match(authContext, /session_expired/, 'expired sessions need an explicit state');
assert.match(authContext, /reauthentication_required/, 'recent-auth failures need an explicit state');
assert.match(authContext, /permission_forbidden/, 'permission failures need an explicit state');
assert.match(authContext, /getRequestState/, 'consumers need explicit request failure classification');
assert.match(authContext, /unavailable/, 'session service failures must have a blocked state');
assert.match(storeContext, /useAuthContext/, 'backend store loading must follow authenticated session state');
assert.match(storeContext, /isBackendSource\s*&&\s*!isAuthenticated/, 'backend stores must not load before login');
const shippingPage = await readFile(new URL('../src/pages/ShippingAssistant.jsx', import.meta.url), 'utf8');
const customerPage = await readFile(new URL('../src/pages/CustomerService.jsx', import.meta.url), 'utf8');
assert.match(shippingPage, /platformWriteEnabled/, 'shipping UI must fail closed when platform writes are disabled');
assert.match(customerPage, /platformReplyEnabled/, 'customer reply UI must fail closed when platform sends are disabled');
assert.match(customerPage, /relatedOrder/, 'customer inquiry detail must display its related order and logistics context');
assert.match(await readFile(new URL('../src/routes/index.jsx', import.meta.url), 'utf8'), /type="unavailable"/, 'unavailable sessions must not render operator routes');
for (const endpoint of ['login:', 'verifyMfa:', 'getSession:', 'logout:', 'getLocalMfaCode:']) {
  assert.match(backendApi, new RegExp(endpoint), `missing auth API wrapper: ${endpoint}`);
}
assert.match(backendApi, /getLocalMfaCode:\s*\(\)\s*=>\s*getData\('\/auth\/local-mfa-code'\)/, 'local MFA code must use the frozen GET endpoint');
assert.match(authPage, /getLocalMfaCode/, 'MFA page must request the local test code');
assert.match(authPage, /status\s*===\s*'mfa_required'/, 'local MFA code must be gated by mfa_required status');
assert.match(authPage, /localMfaDigits|mfa-code-digit/, 'MFA page must render stable digit cells');
assert.match(authPage, /填入验证码/, 'MFA page must provide a fill-code command');
assert.match(authPage, /mfa_invalid/, 'MFA page must support mfa_invalid errors');
assert.match(authPage, /invalid_mfa_code/, 'MFA page must support invalid_mfa_code errors');
assert.doesNotMatch(authPage, /localStorage|sessionStorage|console\./i, 'local MFA code must not be persisted or logged');
const authStyles = await readFile(new URL('../src/styles/global.css', import.meta.url), 'utf8');
assert.match(authStyles, /mfa-code-digit/, 'MFA digit cells need explicit stable styling');

console.log('frontend session security contract: ok');
