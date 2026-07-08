async (page) => {
  const base = 'output/playwright/operator-ready-1';
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];

  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) consoleMessages.push(`${msg.type()}: ${msg.text()}`);
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`);
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`http://127.0.0.1:5180/?operatorReady=${Date.now()}#/settings`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.getByRole('button', { name: '交付检查' }).click();
  await page.waitForTimeout(800);

  const pageText = await page.locator('body').innerText();
  await page.screenshot({ path: `${base}/01-operator-readiness.png`, fullPage: true });

  return {
    readinessTabVisible: pageText.includes('运营试用交付检查'),
    dataSourceVisible: pageText.includes('当前数据源'),
    writeClosedVisible: pageText.includes('平台写入关闭'),
    sopVisible: pageText.includes('运营 SOP'),
    questionMarkRuleVisible: pageText.includes('不是 0'),
    backupVisible: pageText.includes('备份状态'),
    consoleMessages,
    pageErrors,
    failedRequests,
  };
}
