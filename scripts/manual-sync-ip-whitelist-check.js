async (page) => {
  const base = 'output/playwright/manual-sync';
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];
  const apiCalls = [];
  let manualSyncPayload = null;
  let manualSyncResponse = null;

  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) {
      consoleMessages.push(`${msg.type()}: ${msg.text()}`);
    }
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`);
  });

  const ok = (route, data) => route.fulfill({
    status: 200,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify({ success: true, message: 'ok', data }),
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const apiPath = request.url().split('/api/v1')[1] || '/';
    const path = apiPath.split('?')[0].split('#')[0] || '/';
    apiCalls.push(`${request.method()} ${path}`);

    if (request.method() === 'GET' && path === '/stores') {
      return ok(route, {
        items: [{
          id: 101,
          name: 'Coupang 白名单店',
          platform: 'coupang',
          country: 'KR',
          language: 'ko-KR',
          status: 'active',
          owner_name: '运营',
          product_count: null,
          remark: 'Playwright intercepted store',
        }],
        total: 1,
        page: 1,
        page_size: 100,
      });
    }

    if (request.method() === 'POST' && path === '/sync/manual-batch') {
      manualSyncPayload = request.postDataJSON();
      manualSyncResponse = {
        status: 'failed',
        store_id: 101,
        store_platform: 'coupang',
        requested_platforms: ['coupang'],
        replace_policy: 'delete_absent_when_full_snapshot',
        delete_policy: 'delete_absent_only_when_full_snapshot_confirmed',
        platform_write: false,
        items: [
          {
            status: 'failed',
            platform: 'coupang',
            resource: 'products',
            message: 'Coupang：IP 白名单未通过',
            error_code: 'ip_not_allowed',
            created_count: 0,
            updated_count: 0,
            skipped_count: 0,
            deleted_count: 0,
            full_snapshot: false,
            delete_executed: false,
            platform_write: false,
          },
          {
            status: 'failed',
            platform: 'coupang',
            resource: 'orders',
            message: 'Coupang：IP 白名单未通过',
            error_code: 'ip_not_allowed',
            created_count: 0,
            updated_count: 0,
            skipped_count: 0,
            deleted_count: 0,
            full_snapshot: false,
            delete_executed: false,
            platform_write: false,
          },
          {
            status: 'skipped',
            platform: 'coupang',
            resource: 'customer_inquiries',
            message: '客服消息暂未接入真实平台',
            error_code: 'not_open',
            created_count: 0,
            updated_count: 0,
            skipped_count: 0,
            deleted_count: 0,
            full_snapshot: false,
            delete_executed: false,
            platform_write: false,
          },
        ],
        summary: {
          success_count: 0,
          failed_count: 2,
          skipped_count: 1,
          created_count: 0,
          updated_count: 0,
          deleted_count: 0,
        },
      };
      return ok(route, manualSyncResponse);
    }

    if (request.method() === 'GET' && path === '/dashboard/summary') {
      return ok(route, {
        store_count: 1,
        product_count: 0,
        order_count: 0,
        total_sales_amount: 0,
        open_customer_inquiries: 0,
        open_appeal_cases: 0,
        unread_important_emails: 0,
        currency: 'KRW',
        business_timezone: 'Asia/Seoul',
        risk_flags: [],
        latest_sync_logs: [],
        recent_orders: [],
      });
    }

    if (request.method() === 'GET' && ['/products', '/orders', '/customer-inquiries', '/sync-logs'].includes(path)) {
      return ok(route, { items: [], total: 0, page: 1, page_size: 10 });
    }

    if (request.method() === 'GET' && path === '/ai/daily-context') {
      return ok(route, null);
    }

    return ok(route, {});
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`http://127.0.0.1:5179/?manual_ip_check=${Date.now()}#/workbench`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(700);
  await page.getByRole('button', { name: '手动同步' }).waitFor({ state: 'visible' });

  await page.getByRole('button', { name: '手动同步' }).click();
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${base}/03-coupang-ip-whitelist-status.png`, fullPage: true });

  const statusText = await page.locator('.manual-sync-status').innerText();
  const modalText = await page.locator('.manual-sync-result').innerText();
  const dangerousCalls = apiCalls.filter((item) => /writeback|price|stock|inventory|reply|appeal/i.test(item));
  const platformWrites = (manualSyncResponse?.items || []).filter((item) => item.platform_write !== false);
  const deletes = (manualSyncResponse?.items || []).filter((item) => item.deleted_count !== 0 || item.delete_executed !== false);

  if (!statusText.includes('最近一次同步：IP 白名单未通过')) {
    throw new Error(`Expected whitelist status chip, received: ${statusText}`);
  }
  if (!modalText.includes('Coupang：IP 白名单未通过')) {
    throw new Error('Expected whitelist message in result modal');
  }
  if (!modalText.includes('本次重新验证仍未通过') || !modalText.includes('服务器出口 IP')) {
    throw new Error('Expected recheck guidance in result modal');
  }
  if (!manualSyncPayload || Number(manualSyncPayload.store_id) !== 101) {
    throw new Error(`Expected manual sync to target store 101, received: ${JSON.stringify(manualSyncPayload)}`);
  }
  if (platformWrites.length || deletes.length || dangerousCalls.length) {
    throw new Error(`Unsafe sync response or calls: ${JSON.stringify({ platformWrites, deletes, dangerousCalls })}`);
  }

  return {
    statusText,
    modalHasIpNotice: modalText.includes('Coupang：IP 白名单未通过'),
    modalHasRecheckGuidance: modalText.includes('本次重新验证仍未通过') && modalText.includes('服务器出口 IP'),
    modalHasLocalOnlyNotice: modalText.includes('只写入本地 ERP'),
    modalHasCustomerNotice: modalText.includes('客服消息暂未接入'),
    manualSyncPayload,
    dangerousCalls,
    platformWrites,
    deletes,
    consoleMessages,
    pageErrors,
    failedRequests,
  };
}
