import { test, expect } from '@playwright/test';

test.describe('POS flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/accounts/login/');
    await page.fill('input[name="username"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/$/);
  });

  test('creates order, pays, and closes', async ({ page }) => {
    await page.goto('/pos/');
    await page.locator('.pos-btn').first().waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.pos-btn').first().click();
    await page.waitForSelector('.cart-item');

    await page.fill('input[placeholder="Cliente (opcional)"]', 'E2E Test');
    await page.fill('input[placeholder="$ desc"]', '0');

    await page.click('button:has-text("Crear orden")');
    await page.waitForSelector('text=Cobrar', { timeout: 10000 });

    await page.click('button:has-text("Cobrar")');
    await page.waitForSelector('text=Cobrar todo', { timeout: 5000 });

    await expect(page.locator('text=Total').last()).toBeVisible();
    await expect(page.locator('text=Cobrar todo')).toBeVisible();
    await expect(page.getByText('Pagar', { exact: true })).toBeVisible();

    await page.click('button:has-text("Cobrar todo")');
    await page.waitForTimeout(500);

    await page.click('button:has-text("Cerrar orden")');
    await page.waitForSelector('text=Orden cerrada', { timeout: 10000 });

    await expect(page.locator('text=Orden cerrada')).toBeVisible();
    await expect(page.locator('text=Ver recibo')).toBeVisible();
  });

  test('creates order with multiple items and sees correct total', async ({ page }) => {
    await page.goto('/pos/');
    await page.locator('.pos-btn').first().waitFor({ state: 'visible', timeout: 10000 });

    const buttons = page.locator('button.pos-btn');
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(2);

    await buttons.nth(0).click();
    await buttons.nth(1).click();
    await buttons.nth(1).click();

    const cartItems = page.locator('.cart-item');
    await expect(cartItems).toHaveCount(2);

    await page.fill('input[placeholder="Cliente (opcional)"]', 'Multi-item');
    await page.click('button:has-text("Crear orden")');
    await page.waitForSelector('text=Cobrar', { timeout: 10000 });
    await page.click('button:has-text("Cobrar")');
    await page.waitForSelector('text=Cobrar todo', { timeout: 5000 });
    await page.click('button:has-text("Cobrar todo")');
    await page.waitForTimeout(500);
    await page.click('button:has-text("Cerrar orden")');
    await page.waitForSelector('text=Orden cerrada', { timeout: 10000 });
  });
});
