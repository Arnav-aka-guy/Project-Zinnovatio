import { test, expect, type Page } from '@playwright/test';

/**
 * Notifications end to end: the staff bell and inbox, the deep link to a request,
 * "Messages sent" in the request details, the officer delivery card, turning on
 * device alerts (staff and driver), and a real push event reaching the service
 * worker and showing a system notification.
 *
 * Runs in the `push` project (service workers allowed, notifications granted).
 * The browser's own push service (FCM) is not reachable from a test machine, so
 * PushManager.subscribe is replaced by a stand-in that returns a subscription
 * with real-format keys. The push event itself is delivered to the real service
 * worker through Chrome DevTools (ServiceWorker.deliverPushMessage).
 */
const PASS = { 'X-Vaari-Passcode': 'change-me' };
// A real P-256 public key (65 bytes), so the server accepts and can encrypt for it.
const P256DH = 'BA3_HLVkpzU68RDmDk_mMxOP8EvZypf91eQ8qfnmOMIhlGfy6UcQWSO0q4ABrlCafcD2ALe2xU-e0HMXgRWfISg';
const AUTH = 'MDEyMzQ1Njc4OWFiY2RlZg';

async function signIn(page: Page) {
  const box = page.locator('#passcode-input');
  if (await box.isVisible({ timeout: 1500 }).catch(() => false)) {
    await box.fill('change-me');
    await page.locator('#passcode-submit').click();
  }
}

/** Stand-in for the browser push service: one fake subscription per service worker registration. */
async function fakePushService(page: Page) {
  await page.addInitScript(
    ({ p256dh, auth }) => {
      const subs = new Map<string, unknown>();
      const proto = PushManager.prototype as unknown as Record<string, unknown>;
      const b64 = (s: string) => {
        const raw = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4));
        return Uint8Array.from(raw, c => c.charCodeAt(0)).buffer;
      };
      function scopeOf(pm: unknown): string {
        // Each registration has its own PushManager; key the fake by the registration scope.
        return (pm as { __scope?: string }).__scope ?? 'root';
      }
      const origGetReg = navigator.serviceWorker.getRegistration.bind(navigator.serviceWorker);
      const tag = (reg: ServiceWorkerRegistration | undefined) => {
        if (reg) (reg.pushManager as unknown as { __scope?: string }).__scope = new URL(reg.scope).pathname;
        return reg;
      };
      navigator.serviceWorker.getRegistration = (u?: string) => origGetReg(u).then(tag);
      const origRegister = navigator.serviceWorker.register.bind(navigator.serviceWorker);
      navigator.serviceWorker.register = (url: string | URL, opts?: RegistrationOptions) =>
        origRegister(url, opts).then(r => tag(r) as ServiceWorkerRegistration);
      proto.subscribe = async function (this: unknown, opts: PushSubscriptionOptionsInit) {
        const scope = scopeOf(this);
        const endpoint = `https://fcm.googleapis.com/fcm/send/e2e-${scope.replace(/\W/g, '') || 'root'}`;
        const sub = {
          endpoint,
          expirationTime: null,
          options: { applicationServerKey: opts.applicationServerKey, userVisibleOnly: true },
          getKey: (name: string) => b64(name === 'auth' ? auth : p256dh),
          toJSON: () => ({ endpoint, expirationTime: null, keys: { p256dh, auth } }),
          unsubscribe: async () => {
            subs.delete(scope);
            return true;
          },
        };
        subs.set(scope, sub);
        return sub;
      };
      proto.getSubscription = async function (this: unknown) {
        return subs.get(scopeOf(this)) ?? null;
      };
    },
    { p256dh: P256DH, auth: AUTH },
  );
}

test.describe('notifications', () => {
  test('bell shows the role alerts and opens the request they are about', async ({ page }) => {
    await page.goto('/desk');
    await signIn(page);
    const count = page.locator('#alerts-count');
    await expect(count).toBeVisible();
    const before = Number(await count.textContent());
    expect(before).toBeGreaterThan(0); // the demo data has requests that will miss

    await page.locator('#btn-alerts').click();
    const panel = page.locator('#alerts-panel');
    await expect(panel).toBeVisible();
    const first = panel.locator('.alert-item[data-kind="will_miss"]').first();
    await expect(first).toContainText('will miss its deadline');
    const title = (await first.locator('.alert-title').textContent()) ?? '';
    const vr = title.match(/VR-(\d+)/)?.[1];
    await first.click();

    // The alert opened the desk with that request's details.
    await expect(page.locator('#request-detail-panel')).toBeVisible();
    await expect(page.locator('#request-detail-panel')).toContainText(`VR-${vr}`);
    await expect(page).toHaveURL(/\/desk$/); // the deep link is cleaned up
    await expect(count).toHaveText(String(before - 1));

    await page.getByRole('button', { name: 'Close panel' }).click();
    await page.locator('#btn-alerts').click();
    await page.locator('#btn-alerts-read-all').click();
    await expect(page.locator('#alerts-count')).toHaveCount(0);
  });

  test('request details list the messages sent to the farmer', async ({ page }) => {
    await page.goto('/desk');
    await signIn(page);
    const scheduled = page.locator('tr.clickable-row', { hasText: /scheduled/i }).first();
    await scheduled.click();
    const msgs = page.locator('#farmer-messages');
    await expect(msgs).toBeVisible();
    // Demo data is never sent to a real phone: each farmer message is simulated (or held back if out of date).
    const item = msgs.locator('.msg-item[data-status="simulated"]').first();
    await expect(item).toContainText('to farmer by SMS');
    await expect(item).toContainText('ਸਤ ਸ੍ਰੀ ਅਕਾਲ');
    await expect(item.locator('.msg-status')).toHaveText('Simulated');
    await expect(item).toContainText('demo data, not sent');
    await expect(msgs.locator('.msg-status.s-sent')).toHaveCount(0);
  });

  test('officer sees whether messages are going out', async ({ page }) => {
    await page.goto('/officer');
    await signIn(page);
    const card = page.locator('#delivery-card');
    await expect(card).toBeVisible();
    await expect(card).toContainText('Demo mode: farmer messages are recorded, not sent');
    await expect(card).toContainText('To farmers (SMS/WhatsApp)');
    await expect(card).toContainText('Simulated');
  });

  test('staff turn on alerts, and a push event shows a system notification', async ({ page, context }) => {
    await fakePushService(page);
    await page.goto('/desk');
    await signIn(page);
    await page.locator('#btn-alerts').click();
    await page.locator('#btn-alerts-on').click();
    await expect(page.locator('#alerts-device')).toContainText('Alerts on this device');
    await expect(page.locator('#btn-alerts-test')).toBeVisible();

    const summary = await (await page.request.get('/api/notify/summary', { headers: PASS })).json();
    expect(summary.devices.staff).toBe(1);

    // Deliver a real push event to the service worker.
    const cdp = await context.newCDPSession(page);
    const regs: { registrationId: string; scopeURL: string }[] = [];
    cdp.on('ServiceWorker.workerRegistrationUpdated', e => regs.push(...e.registrations));
    await cdp.send('ServiceWorker.enable');
    await expect.poll(() => regs.find(r => new URL(r.scopeURL).pathname === '/')?.registrationId).toBeTruthy();
    const reg = regs.find(r => new URL(r.scopeURL).pathname === '/')!;
    const origin = new URL(page.url()).origin;
    const payload = {
      id: 1,
      kind: 'will_miss',
      title: 'VR-999 will miss its deadline',
      body: 'Pind Test · 2 ac · Super Seeder',
      url: '/officer',
      tag: 'vaari-will_miss-999',
      urgency: 'high',
    };
    await cdp.send('ServiceWorker.deliverPushMessage', {
      origin,
      registrationId: reg.registrationId,
      data: JSON.stringify(payload),
    });
    await expect
      .poll(() =>
        page.evaluate(async () => {
          const r = await navigator.serviceWorker.getRegistration('/');
          const list = r ? await r.getNotifications() : [];
          return list.map(n => `${n.title}|${n.body}|${n.tag}`);
        }),
      )
      .toContain('VR-999 will miss its deadline|Pind Test · 2 ac · Super Seeder|vaari-will_miss-999');

    await page.locator('#btn-alerts-off').click();
    await expect(page.locator('#btn-alerts-on')).toBeVisible();
    const after = await (await page.request.get('/api/notify/summary', { headers: PASS })).json();
    expect(after.devices.staff).toBe(0);
  });

  test('driver turns on job alerts from the driver link', async ({ page }) => {
    await fakePushService(page);
    const machines = await (await page.request.get('/api/machines', { headers: PASS })).json();
    const driverPath = machines[0].driver_path as string;
    await page.goto(driverPath);
    const card = page.locator('#driver-alerts');
    await expect(card).toBeVisible();
    await page.locator('#btn-driver-alerts-on').click();
    await expect(card).toContainText('Job alerts are on');
    const summary = await (await page.request.get('/api/notify/summary', { headers: PASS })).json();
    expect(summary.devices.driver).toBe(1);
    // The driver link has no staff menu and no staff bell.
    await expect(page.locator('#btn-alerts')).toHaveCount(0);
  });

  test('on a phone the alerts open as a bottom sheet that fits the screen', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/desk');
    await signIn(page);
    const bell = page.locator('#btn-alerts');
    await expect(bell).toBeVisible();
    const box = await bell.boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
    expect(box!.height).toBeGreaterThanOrEqual(40);
    await bell.click();
    const sheet = page.locator('#alerts-panel.sheet');
    await expect(sheet).toBeVisible();
    const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollW).toBeLessThanOrEqual(391);
    await expect(sheet.locator('.alert-item').first()).toBeVisible();
  });
});
