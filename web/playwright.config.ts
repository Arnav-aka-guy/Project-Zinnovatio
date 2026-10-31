import { defineConfig, devices } from '@playwright/test';

// iPhone 13 size, touch and user agent, run on the Chromium that is installed.
const { defaultBrowserType: _webkit, ...iphone } = devices['iPhone 13'];
void _webkit;

export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:8000',
    trace: 'off',
    video: 'off',
    screenshot: 'only-on-failure',
    // Optional: point at a preinstalled Chromium when the bundled revision is absent.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
  projects: [
    {
      name: 'chromium',
      testIgnore: /(mobile|notifications)\.spec\.ts/,
      // The app's service worker would hide requests from page.route() mocks.
      use: { ...devices['Desktop Chrome'], serviceWorkers: 'block' },
    },
    // Phone web app (e2e/mobile.spec.ts), Chromium engine at phone sizes with touch.
    {
      name: 'mobile-android',
      testMatch: /mobile\.spec\.ts/,
      use: { ...devices['Pixel 7'], serviceWorkers: 'block' },
    },
    {
      name: 'mobile-iphone',
      testMatch: /mobile\.spec\.ts/,
      use: { ...iphone, serviceWorkers: 'block' },
    },
    // Alerts (e2e/notifications.spec.ts): needs the real service worker and notification permission.
    // On Windows, Chromium requires a window handle for the notification platform bridge.
    {
      name: 'push',
      testMatch: /notifications\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        serviceWorkers: 'allow',
        permissions: ['notifications'],
        headless: process.platform === 'win32' ? false : true,
        launchOptions: process.platform === 'win32' ? { args: ['--window-position=-2400,-2400'] } : {},
      },
    },
  ],
});
