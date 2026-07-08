async (page) => {
  const base = 'output/playwright/core-pages-polish';
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
  const shots = [];

  async function visit(route, name) {
    await page.goto(`http://127.0.0.1:5173/#${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(900);
    const file = `${base}/${name}.png`;
    await page.screenshot({ path: file, fullPage: true });
    shots.push({ name, route, path: file, url: page.url() });
  }

  await visit('/workbench', '01-core-workbench');
  await visit('/orders', '02-core-orders');
  const orderDetailButtons = await page.getByRole('button', { name: '详情' }).count();
  if (orderDetailButtons) {
    await page.getByRole('button', { name: '详情' }).first().click();
    await page.waitForTimeout(500);
    const file = `${base}/03-core-order-detail.png`;
    await page.screenshot({ path: file, fullPage: true });
    shots.push({ name: '03-core-order-detail', route: '/orders', path: file, url: page.url() });
  }

  await visit('/shipping', '04-core-shipping');
  await visit('/products', '05-core-products');
  const productDetailButtons = await page.getByRole('button', { name: '详情' }).count();
  if (productDetailButtons) {
    await page.getByRole('button', { name: '详情' }).first().click();
    await page.waitForTimeout(500);
    const file = `${base}/06-core-product-detail.png`;
    await page.screenshot({ path: file, fullPage: true });
    shots.push({ name: '06-core-product-detail', route: '/products', path: file, url: page.url() });
  }

  await visit('/inventory', '07-core-inventory');

  return {
    shots,
    consoleMessages,
    pageErrors,
    failedRequests,
  };
}
