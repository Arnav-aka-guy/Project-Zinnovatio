import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

/**
 * Phone web app: every screen and every main feature at phone size.
 * Runs in the `mobile-android` (Pixel 7) and `mobile-iphone` (iPhone 13 size) projects.
 */
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIX = (name: string) => path.resolve(__dirname, '../../tests/fixtures', name);
const PASS = { 'X-Vaari-Passcode': 'change-me' };

async function signIn(page: Page) {
  const box = page.locator('#passcode-input');
  if (await box.isVisible({ timeout: 1500 }).catch(() => false)) {
    await box.fill('change-me');
    await page.locator('#passcode-submit').click();
  }
}

/** The page must fit the phone: nothing wider than the screen. */
async function expectFitsScreen(page: Page) {
  const { scrollW, vw } = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    vw: window.innerWidth,
  }));
  expect(scrollW, 'page is wider than the phone screen').toBeLessThanOrEqual(vw + 1);
}

/** Main controls are big enough to tap (44 px guideline, 40 px floor). */
async function expectTappable(page: Page, selector: string) {
  const boxes = await page.locator(selector).evaluateAll(els =>
    els
      .filter(e => (e as HTMLElement).offsetParent !== null)
      .map(e => {
        const b = e.getBoundingClientRect();
        return { w: b.width, h: b.height, id: e.id || e.textContent?.trim().slice(0, 20) };
      }),
  );
  for (const b of boxes) {
    expect(b.h, `${b.id} is too short to tap`).toBeGreaterThanOrEqual(40);
    expect(b.w, `${b.id} is too narrow to tap`).toBeGreaterThanOrEqual(40);
  }
}

/** iOS zooms into inputs with text under 16 px. */
async function expectNoZoomInputs(page: Page) {
  const small = await page
    .locator('input:not([type=checkbox]):not([type=radio]):not([type=file]):not([type=hidden]), select, textarea')
    .evaluateAll(els =>
      els
        .filter(e => (e as HTMLElement).offsetParent !== null)
        .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16)
        .map(e => e.id || e.tagName),
    );
  expect(small, 'inputs under 16px make iPhones zoom').toEqual([]);
}

async function scheduledSlot(request: APIRequestContext) {
  const machines = await (await request.get('/api/machines', { headers: PASS })).json();
  for (const m of machines) {
    const token = String(m.driver_path).split('/').pop();
    const view = await (await request.get(`/api/driver/${token}`)).json();
    const slot = (view.slots ?? []).find((s: { status: string }) => s.status === 'scheduled');
    if (slot) return { driverPath: m.driver_path as string, slotId: slot.id as number };
  }
  return null;
}

test.describe('phone web app', () => {
  test('app shell: tab bar, More sheet, every page fits the screen', async ({ page }) => {
    await page.goto('/desk');
    await signIn(page);
    await expect(page.locator('#desk-page')).toBeVisible();

    // Desktop menu hidden, phone tab bar shown.
    await expect(page.locator('.nav-links')).toBeHidden();
    const tabbar = page.locator('nav.tabbar');
    await expect(tabbar).toBeVisible();
    const bar = await tabbar.boundingBox();
    const vh = page.viewportSize()!.height;
    expect(bar!.y + bar!.height).toBeGreaterThanOrEqual(vh - 1); // pinned to the bottom
    await expectTappable(page, 'nav.tabbar .tabbar-item');

    const pages: [string, string, string][] = [
      ['#mnav-voice', '/voice', 'Voice booking'],
      ['#mnav-intake', '/intake', 'Register photo'],
      ['#mnav-officer', '/officer', 'Officer'],
      ['#mnav-desk', '/desk', 'Desk'],
    ];
    for (const [tab, url, title] of pages) {
      await page.locator(tab).click();
      await expect(page).toHaveURL(new RegExp(`${url}$`));
      await expect(page.locator('.brand-page')).toHaveText(title);
      await expect(page.locator(tab)).toHaveClass(/active/);
      await page.waitForLoadState('networkidle');
      await expectFitsScreen(page);
      await expectNoZoomInputs(page);
    }

    // More sheet: driver links and records.
    await page.locator('#mnav-more').click();
    await expect(page.locator('#more-sheet')).toBeVisible();
    await page.locator('#mnav-driver').click();
    await expect(page).toHaveURL(/\/driver$/);
    await expect(page.locator('#more-sheet')).toBeHidden();
    await expectFitsScreen(page);
    await page.locator('#mnav-more').click();
    await page.locator('#mnav-record').click();
    await expect(page).toHaveURL(/\/record$/);
    await expectFitsScreen(page);
  });

  test('desk: new request from the phone, request card, detail sheet, tabs', async ({ page }) => {
    await page.goto('/desk');
    await signIn(page);
    await expect(page.locator('#desk-page')).toBeVisible();
    await expectFitsScreen(page);

    // The form is folded away until asked for (no keyboard popping up on open).
    await expect(page.locator('#new-request-form')).toHaveCount(0);
    await page.locator('#btn-open-new-request').click();
    await expect(page.locator('#req-phone')).toBeFocused();
    await expectNoZoomInputs(page);

    const phone = `9${String(Date.now()).slice(-9)}`;
    await page.locator('#req-phone').fill(phone);
    await page.locator('#req-name').fill('Mobile Test');
    await page.locator('#req-village').fill('Pind Kalan');
    await page.locator('#req-acres').fill('2.5');
    await page.locator('#btn-service-happy_seeder').click();
    await page.locator('#req-not-cut').check();
    await page.locator('#btn-submit-request').click();
    await expect(page.locator('.outcome-banner').first()).toBeVisible();
    await page.locator('#btn-close-new-request').click();
    await expect(page.locator('#btn-open-new-request')).toBeVisible();

    // Request cards: the new one is there and opens the full-screen detail.
    const card = page.locator('#desk-requests-table tr', { hasText: phone });
    await expect(card).toBeVisible();
    const box = await card.boundingBox();
    expect(box!.width).toBeGreaterThan(page.viewportSize()!.width * 0.85);
    await card.click();
    const sheet = page.locator('#request-detail-panel .side-panel');
    await expect(sheet).toBeVisible();
    const sb = await sheet.boundingBox();
    expect(sb!.width).toBeGreaterThanOrEqual(page.viewportSize()!.width - 1);
    await expectTappable(page, '#request-detail-panel .panel-close-btn');
    await page.locator('#request-detail-panel .panel-close-btn').click();
    await expect(page.locator('#request-detail-panel')).toHaveCount(0);

    // Tabs scroll in one row and stay reachable.
    for (const tab of ['#tab-will-miss', '#tab-machines', '#tab-map', '#tab-requests']) {
      await page.locator(tab).click();
      await expect(page.locator(tab)).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator(tab)).toBeInViewport();
      await expectFitsScreen(page);
    }
    await page.locator('#tab-machines').click();
    await expect(page.locator('#machine-card-1')).toBeVisible();
    await expectFitsScreen(page);
  });

  test('register photo: camera button, draft rows as cards, confirm', async ({ page }) => {
    await page.goto('/intake');
    await signIn(page);
    await expect(page.locator('label[for="intake-file-input"]')).toBeVisible();
    await expect(page.locator('#intake-file-input')).toHaveAttribute('capture', 'environment');
    await expectTappable(page, '.upload-btn');

    await page.locator('#intake-file-input').setInputFiles(FIX('register_page.jpg'));
    await expect(page.locator('#intake-draft-table')).toBeVisible({ timeout: 15000 });
    await expectFitsScreen(page);
    await expectNoZoomInputs(page);

    // Each drafted row reads as a card with labelled fields.
    const firstCell = page.locator('#intake-draft-table tbody tr').first().locator('td').nth(1);
    await expect(firstCell).toHaveAttribute('data-label', /.+/);

    // Rows with problems are skipped so the rest can be confirmed.
    const rows = page.locator('#intake-draft-table tbody tr');
    const n = await rows.count();
    for (let i = 0; i < n; i++) {
      const bad = await rows.nth(i).locator('.field-error-msg, [class*="error"]').count();
      if (bad) await rows.nth(i).locator('input[type=checkbox]').last().check();
    }
    const confirm = page.locator('#btn-confirm-rows');
    await confirm.scrollIntoViewIfNeeded();
    await confirm.click();
    await expect(page.locator('#intake-confirm-banner')).toBeVisible({ timeout: 15000 });
  });

  test('voice booking works by touch and typing on a phone', async ({ page, context }) => {
    await context.addInitScript(() => {
      (window as unknown as Record<string, unknown>).webkitSpeechRecognition = undefined;
      (window as unknown as Record<string, unknown>).SpeechRecognition = undefined;
    });
    await page.goto('/voice');
    await signIn(page);
    await page.getByRole('button', { name: /Start in English/ }).click();
    await expectFitsScreen(page);

    const yes = page.getByRole('button', { name: /ਹਾਂ ਜੀ \/ Yes/ });
    const typeAndConfirm = async (text: string) => {
      await page.locator('#vb-typed').fill(text);
      await page.locator('#vb-typed').press('Enter');
      await yes.click();
    };
    await typeAndConfirm(`9${String(Date.now()).slice(-9)}`);
    await typeAndConfirm('Talwandi Sabo');
    await typeAndConfirm('3');
    await page.getByRole('button', { name: /Baler/ }).click();
    await yes.click();
    await page.getByRole('button', { name: /Not known yet/ }).click();
    await yes.click();
    await expectFitsScreen(page);
    await page.getByRole('button', { name: /Confirm booking/ }).click();
    await expect(page.locator('.vb-done')).toBeVisible({ timeout: 30000 });
    await expectFitsScreen(page);
  });

  test('officer dashboard fits and its tables read as cards', async ({ page }) => {
    await page.goto('/officer');
    await signIn(page);
    await page.waitForLoadState('networkidle');
    await expectFitsScreen(page);
    const labelled = page.locator('table.is-labelled td[data-label]');
    expect(await labelled.count()).toBeGreaterThan(0);
  });

  test('driver link: no staff menu, start and finish a job with photos, then the record', async ({
    page,
    context,
    request,
  }) => {
    const found = await scheduledSlot(request);
    test.skip(!found, 'no scheduled job left today');
    const { driverPath, slotId } = found!;
    const msg = await (await request.get(`/api/slots/${slotId}/message`, { headers: PASS })).json();
    const code = String(msg.body_en).match(/code:\s*(\d{4})/)![1];

    await context.grantPermissions(['geolocation']);
    await context.setGeolocation({ latitude: 30.7333, longitude: 76.7794 });
    await page.goto(driverPath);
    await expect(page.locator('#driver-page')).toBeVisible();
    await expect(page.locator('nav.tabbar')).toHaveCount(0);
    await expect(page.locator('.nav-links')).toHaveCount(0);
    await expectFitsScreen(page);

    await page.locator('.driver-job-card.card-status-scheduled').first().click();
    const sheet = page.locator('.driver-action-card');
    await expect(sheet).toBeVisible();
    await expectTappable(page, '.cab-close-btn, #btn-start-job, #btn-open-not-served');

    await page.locator('#driver-camera-input').setInputFiles(FIX('start_field.jpg'));
    await page.locator('#btn-start-job').click();
    await expect(page.locator('#evidence-summary-ticks')).toBeVisible({ timeout: 15000 });
    await page.locator('#btn-continue-job').click();

    await page.locator('#driver-camera-input-done').setInputFiles(FIX('done_field.jpg'));
    await page.locator('#farmer-code-input').fill(code);
    await expectNoZoomInputs(page);
    await page.locator('#btn-done-job').click();
    await expect(page.locator('#evidence-summary-ticks')).toBeVisible({ timeout: 15000 });

    await page.locator('#btn-view-record-link').click();
    await expect(page.locator('#record-page')).toBeVisible();
    await expect(page.locator('nav.tabbar')).toHaveCount(0);
    await expectFitsScreen(page);
    await page.locator('#btn-verify-hash').click();
    await expectFitsScreen(page);
  });

  test.describe('installable web app', () => {
    test.use({ serviceWorkers: 'allow' });

    test('manifest, icons and offline app shell', async ({ page, context, request }) => {
      await page.goto('/desk');
      await signIn(page);
      const href = await page.locator('link[rel="manifest"]').getAttribute('href');
      const manifest = await (await request.get(href!)).json();
      expect(manifest.short_name).toBe('Vaari');
      expect(manifest.display).toBe('standalone');
      expect(manifest.start_url).toMatch(/^\/desk/);
      const sizes = manifest.icons.map((i: { sizes: string }) => i.sizes);
      expect(sizes).toEqual(expect.arrayContaining(['192x192', '512x512']));
      expect(manifest.icons.some((i: { purpose?: string }) => i.purpose === 'maskable')).toBe(true);
      for (const icon of manifest.icons) {
        const res = await request.get(icon.src);
        expect(res.status()).toBe(200);
        expect(res.headers()['content-type']).toContain('image/png');
      }
      await expect(page.locator('meta[name="theme-color"]')).toHaveCount(1);
      await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveCount(1);

      // Service worker takes control, then the app opens with no network.
      await page.evaluate(async () => {
        await navigator.serviceWorker.ready;
      });
      await page.reload();
      await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
      await page.waitForLoadState('networkidle');

      await context.setOffline(true);
      await page.goto('/officer').catch(() => undefined);
      await expect(page.locator('nav.tabbar')).toBeVisible();
      await expect(page.locator('.offline-bar')).toBeVisible();
      await context.setOffline(false);
      await expect(page.locator('.offline-bar')).toBeHidden();
    });
  });
});
