async (page) => {
  const base = 'output/playwright/manual-sync';
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];

  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) {
      consoleMessages.push(`${msg.type()}: ${msg.text()}`);
    }
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`);
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`http://127.0.0.1:5178/?manual_sync_check=${Date.now()}#/workbench`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${base}/01-topbar-manual-sync.png`, fullPage: true });

  await page.getByRole('button', { name: '手动同步' }).click();
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${base}/02-manual-sync-result.png`, fullPage: true });

  const statusText = await page.locator('.manual-sync-status').innerText();
  const modalText = await page.locator('.manual-sync-result').innerText();

  return {
    statusText,
    modalHasLocalOnlyNotice: modalText.includes('只写入本地 ERP'),
    modalHasCustomerResult: modalText.includes('客服消息'),
    consoleMessages,
    pageErrors,
    failedRequests,
  };
}
