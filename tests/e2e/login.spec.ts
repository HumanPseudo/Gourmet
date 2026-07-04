import { test, expect } from '@playwright/test';

test.describe('Login flow', () => {
  test('logs in with valid credentials and sees POS link', async ({ page }) => {
    await page.goto('/accounts/login/');
    await page.fill('input[name="username"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await expect(page.locator('nav a:has-text("POS")').first()).toBeVisible();
  });

  test('shows error with invalid credentials', async ({ page }) => {
    await page.goto('/accounts/login/');
    await page.fill('input[name="username"]', 'wrong@example.com');
    await page.fill('input[name="password"]', 'wrong');
    await page.click('button[type="submit"]');
    await expect(page.locator('text=Email o contraseña incorrectos')).toBeVisible();
  });
});
