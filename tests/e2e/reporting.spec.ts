import { test, expect } from '@playwright/test';

test.describe('Dashboard & reporting', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/accounts/login/');
    await page.fill('input[name="username"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/$/);
  });

  test('dashboard shows sales data', async ({ page }) => {
    await page.goto('/pos/dashboard/');
    await page.waitForSelector('text=Dashboard', { timeout: 10000 });
    await expect(page.locator('.label:has-text("Órdenes")')).toBeVisible();
  });

  test('dashboard date filter works', async ({ page }) => {
    await page.goto('/pos/dashboard/');
    await page.waitForSelector('input[type="date"]', { timeout: 10000 });
    const today = new Date().toISOString().split('T')[0];
    const desde = page.locator('input[name="desde"]');
    const hasta = page.locator('input[name="hasta"]');
    await desde.fill(today);
    await hasta.fill(today);
    await page.click('button:has-text("Filtrar")');
    await page.waitForURL(/\?desde=.+&hasta=.+/);
  });

  test('CSV export downloads', async ({ page }) => {
    await page.goto('/pos/dashboard/');
    await page.waitForSelector('text=CSV', { timeout: 10000 });
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('text=CSV'),
    ]);
    expect(download.suggestedFilename()).toContain('ventas.csv');
  });

  test('close report shows daily summary', async ({ page }) => {
    await page.goto('/pos/close-report/');
    await page.waitForSelector('text=Corte de Caja', { timeout: 10000 });

    await expect(page.locator('.label:has-text("Ventas")')).toBeVisible();
    await expect(page.locator('.label:has-text("Efectivo")')).toBeVisible();
    await expect(page.locator('text=Guardar Corte')).toBeVisible();
  });

  test('close report arqueo form works', async ({ page }) => {
    await page.goto('/pos/close-report/');
    await page.waitForSelector('text=Corte de Caja', { timeout: 10000 });

    await page.fill('input[name="cash_opening"]', '50000');
    await page.fill('input[name="cash_counted"]', '100000');
    await page.click('button:has-text("Guardar Corte")');

    await page.waitForSelector('text=Corte guardado', { timeout: 10000 });
    await expect(page.locator('text=Corte guardado')).toBeVisible();
  });
});
