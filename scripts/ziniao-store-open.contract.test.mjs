import assert from 'node:assert/strict';
import fs from 'node:fs';
import { adaptStore, toBackendStorePayload } from '../src/services/adapters.js';


const read = (path) => fs.readFileSync(path, 'utf8');
const component = read('src/components/common/OpenStoreBackendButton.jsx');
const selector = read('src/components/common/StoreSelector.jsx');
const storeContext = read('src/context/StoreContext.jsx');
const layout = read('src/layouts/AdminLayout.jsx');
const stores = read('src/pages/Stores.jsx');
const orders = read('src/pages/Orders.jsx');
const backendApi = read('src/services/backendApi.js');
const dataProvider = read('src/services/dataProvider.js');
const backendRoute = read('backend/app/api/v1/endpoints/stores.py');
const backendService = read('backend/app/services/platform_login_service.py');
const directoryService = read('backend/app/services/ziniao_directory_sync_service.py');
const backendMain = read('backend/app/main.py');

const store = adaptStore({
  id: 8,
  name: 'PXG',
  platform: 'naver',
  browser_provider: 'ziniao',
  browser_profile_name: 'Exact Ziniao Name',
  ziniao_directory_status: 'active',
  source_platform: 'Naver',
  source_site: 'Korea',
  operational_mode: 'business',
  directory_checked_at: '2026-07-15T12:00:00Z',
  network: {
    ip_address: '8.8.8.8',
    country: 'Korea',
    region: 'Seoul',
    city: 'Seoul',
    status: 'success',
  },
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
assert.equal(store.ziniaoDirectoryStatus, 'active');
assert.equal(store.network.ipAddress, '8.8.8.8');
assert.equal(store.network.status, 'success');
assert.equal(store.openOnly, false);
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
assert.match(stores, /renderExtraActions=\{\(store\) => \([\s\S]*<OpenStoreBackendButton store=\{store\} compact \/>/);
assert.match(stores, /browserProfileName/);
assert.match(stores, /必须与紫鸟店铺列表中的名称完全一致/);
assert.match(stores, /includeArchived/);
assert.match(stores, /store_membership\.assign/);
assert.match(stores, /store\.manage/);
assert.match(stores, /canViewArchived \?/);
assert.match(stores, /\/orders\?view=historical&storeId=/);
assert.match(orders, /deepLinkView === 'historical'/);
assert.match(orders, /归档店铺 #\{deepLinkStoreId\}/);
assert.match(selector, /selectedStore\?\.network/);
assert.match(selector, /IP \$\{network\.ipAddress\}/);
assert.match(selector, /归属查询失败，等待重试/);
assert.match(selector, /动态网络，打开店铺时分配 IP/);
assert.match(storeContext, /refreshSession\(\)[\s\S]*refreshStores\(\{ silent: true, forceRefresh: true \}\)/);
assert.match(backendRoute, /@router\.post\("\/\{store_id\}\/open-backend"\)/);
assert.match(backendRoute, /permission_key="platform\.browser\.open"/);
assert.match(backendRoute, /include_archived: bool/);
assert.match(backendRoute, /Store\.ziniao_directory_status != "removed"/);
assert.match(backendService, /\["--id", external_id\]/);
assert.match(backendService, /not platform_text and directory_source_matches/);
assert.match(backendService, /"store", "open"/);
assert.match(backendService, /"--expected-name", profile_name/);
assert.match(backendService, /"shell": False/);
assert.match(directoryService, /"account", "list", "--page-all"/);
assert.match(directoryService, /https:\/\/ipwho\.is\//);
assert.match(directoryService, /ASSIGNMENT_DIRECTORY = "ziniao_directory"/);
assert.match(directoryService, /store\.ziniao_missing_count >= 2/);
assert.match(directoryService, /raw_response_saved": False/);
assert.match(backendMain, /run_due_ziniao_directory_sync/);
assert.doesNotMatch(backendMain, /asyncio\.create_task\(run_ziniao_directory/);
assert.doesNotMatch(backendService, /shell=True/);
assert.doesNotMatch(component, /storeId.*ziniao|ziniao.*storeId/i);
assert.doesNotMatch(component, /--url|launchUrl|superbrowser:\/\//i);
assert.doesNotMatch(directoryService, /row\.get\("username"\)|row\["username"\]/);

console.log('Ziniao store-open and directory frontend contract passed');
