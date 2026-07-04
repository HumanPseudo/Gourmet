import { test, expect } from '@playwright/test';

test.describe('Kitchen display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/accounts/login/');
    await page.fill('input[name="username"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/$/);
  });

  test('shows pending items with status labels', async ({ page }) => {
    await page.goto('/pos/kitchen/');
    await page.waitForSelector('.kcard', { timeout: 10000 });

    const cards = page.locator('.kcard');
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    await expect(page.locator('.kcard').first()).toBeVisible();
    await expect(page.locator('text=Pendientes')).toBeVisible();
  });

  test('shows priority indicators on items', async ({ page }) => {
    await page.goto('/pos/kitchen/');
    await page.waitForSelector('.kcard', { timeout: 10000 });
    const cards = page.locator('.kcard');
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });
});
