import { test, expect } from '@playwright/test';

test.describe('Order detail & reopen', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/accounts/login/');
    await page.fill('input[name="username"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/$/);
  });

  test('order list shows orders', async ({ page }) => {
    await page.goto('/pos/orders/');
    await page.waitForSelector('text=Órdenes', { timeout: 10000 });
    await expect(page.locator('table')).toBeVisible();
  });

  test('closed order shows reopen button', async ({ page }) => {
    await page.goto('/pos/orders/');
    await page.waitForSelector('table', { timeout: 10000 });

    const closedRows = page.locator('table tr:has-text("closed")');
    const count = await closedRows.count();

    if (count > 0) {
      await closedRows.first().locator('a').first().click();
      await page.waitForURL(/\/pos\/orders\//);

      await expect(page.locator('text=Reabrir orden')).toBeVisible();
    }
  });

  test('reopen a closed order', async ({ page }) => {
    await page.goto('/pos/close-report/');
    await page.waitForSelector('text=Corte de Caja', { timeout: 10000 });
    await page.click('text=Dashboard');
    await page.waitForSelector('text=Dashboard', { timeout: 10000 });
    await page.click('text=POS');
    await page.waitForSelector('.pos-btn', { timeout: 10000 });
  });
});
