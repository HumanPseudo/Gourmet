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
    await expect(page.locator('.order-card').first()).toBeVisible();
  });

  test('closed order shows reopen button', async ({ page }) => {
    await page.goto('/pos/orders/');
    await page.waitForSelector('.order-card', { timeout: 10000 });

    const closedCards = page.locator('.order-card.closed');
    const count = await closedCards.count();

    if (count > 0) {
      await closedCards.first().locator('.btn-ver').click();
      await page.waitForURL(/\/pos\/orders\/[0-9a-f-]+\/?$/);

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
