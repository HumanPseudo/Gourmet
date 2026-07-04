import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:8000',
    headless: true,
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'docker compose run --rm app python manage.py seed_today',
    port: 8000,
    reuseExistingServer: true,
  },
});
