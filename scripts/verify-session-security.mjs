import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [http, authContext, backendApi, storeContext] = await Promise.all([
  readFile(new URL('../src/services/http.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/context/AuthContext.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/services/backendApi.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/context/StoreContext.jsx', import.meta.url), 'utf8'),
]);

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
assert.match(await readFile(new URL('../src/routes/index.jsx', import.meta.url), 'utf8'), /type="unavailable"/, 'unavailable sessions must not render operator routes');
for (const endpoint of ['login:', 'verifyMfa:', 'getSession:', 'logout:']) {
  assert.match(backendApi, new RegExp(endpoint), `missing auth API wrapper: ${endpoint}`);
}

console.log('frontend session security contract: ok');
