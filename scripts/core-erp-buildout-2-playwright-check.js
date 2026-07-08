async (page) => {
  const base = 'output/playwright/core-erp-buildout-2';
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
  await page.goto(`http://127.0.0.1:5180/?buildout2=${Date.now()}#/workbench`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(800);

  const pageText = await page.locator('body').innerText();
  const overviewTitleVisible = pageText.includes('全店铺运营总览');
  const unknownMetricCount = await page.locator('.overview-metric.unknown').count();
  const syncAllVisible = await page.getByRole('button', { name: '同步全部可用店铺' }).isVisible();

  await page.screenshot({ path: `${base}/01-store-overview.png`, fullPage: true });
  await page.getByRole('button', { name: '同步全部可用店铺' }).click();
  await page.waitForFunction(() => {
    const text = document.body.innerText || '';
    return text.includes('全店铺同步完成') || text.includes('全店铺同步失败');
  }, { timeout: 30000 }).catch(() => {});
  const afterSyncText = await page.locator('body').innerText();
  await page.screenshot({ path: `${base}/02-sync-all-feedback.png`, fullPage: true });

  return {
    overviewTitleVisible,
    unknownMetricCount,
    syncAllVisible,
    hasUnknownRuleText: pageText.includes('无法确认时显示“?”'),
    hasIpWhitelistReason: pageText.includes('IP 白名单未通过'),
    syncAllFeedbackVisible: afterSyncText.includes('全店铺同步完成'),
    consoleMessages,
    pageErrors,
    failedRequests,
  };
}
