import assert from 'node:assert/strict';
import fs from 'node:fs';
import { adaptStore, toBackendStorePayload } from '../src/services/adapters.js';


const read = (path) => fs.readFileSync(path, 'utf8');
const component = read('src/components/common/OpenStoreBackendButton.jsx');
const layout = read('src/layouts/AdminLayout.jsx');
const stores = read('src/pages/Stores.jsx');
const backendApi = read('src/services/backendApi.js');
const dataProvider = read('src/services/dataProvider.js');
const backendRoute = read('codex1/backend/app/api/v1/endpoints/stores.py');
const backendService = read('codex1/backend/app/services/platform_login_service.py');

const store = adaptStore({
  id: 8,
  name: 'PXG',
  platform: 'naver',
  browser_provider: 'ziniao',
  browser_profile_name: 'Exact Ziniao Name',
  browser_open_capability: {
    provider: 'ziniao',
    configured: true,
    runtime_enabled: true,
    supported: true,
  },
});
assert.equal(store.browserProvider, 'ziniao');
assert.equal(store.browserProfileName, 'Exact Ziniao Name');
assert.equal(store.browserOpenCapability.configured, true);
assert.equal(store.browserOpenCapability.runtimeEnabled, true);
assert.equal(store.browserOpenCapability.supported, true);
assert.deepEqual(toBackendStorePayload({
  name: 'PXG',
  platform: 'Naver',
  browserProvider: 'ziniao',
  browserProfileName: ' Exact Ziniao Name ',
}), {
  name: 'PXG',
  platform: 'naver',
  country: 'KR',
  language: 'ko-KR',
  status: 'active',
  browser_provider: 'ziniao',
  browser_profile_name: 'Exact Ziniao Name',
});

assert.match(backendApi, /\/stores\/\$\{encodeURIComponent\(storeId\)\}\/open-backend/);
assert.match(dataProvider, /openStoreBackend: async \(storeId\)/);
assert.match(component, /platform\.browser\.open/);
assert.match(component, /dataProvider\.openStoreBackend\(store\.id\)/);
assert.match(component, /打开店铺后台/);
assert.match(component, /capability\.configured/);
assert.match(component, /setState\(\{ status: 'idle', message: '' \}\);[\s\S]*\[store\?\.id\]/);
assert.match(layout, /<OpenStoreBackendButton store=\{selectedStore\} compact \/>/);
assert.match(stores, /renderExtraActions=\{\(store\) => <OpenStoreBackendButton store=\{store\} compact \/>\}/);
assert.match(stores, /browserProfileName/);
assert.match(stores, /必须与紫鸟店铺列表中的名称完全一致/);
assert.match(backendRoute, /@router\.post\("\/\{store_id\}\/open-backend"\)/);
assert.match(backendRoute, /permission_key="platform\.browser\.open"/);
assert.match(backendService, /"store", "open", "--name", profile_name, "--expected-name", profile_name/);
assert.match(backendService, /"shell": False/);
assert.doesNotMatch(backendService, /shell=True/);
assert.doesNotMatch(component, /storeId.*ziniao|ziniao.*storeId/i);
assert.doesNotMatch(component, /--url|launchUrl|superbrowser:\/\//i);

console.log('Ziniao store-open frontend contract passed');
