import { test, expect } from '@playwright/test';

// Step V9: Browser end-to-end test for Voice Booking flow.
// Tests the full flow:
//   1. Open /voice
//   2. See automated assistant notice and grant consent
//   3. Tap mic to record farmer speech
//   4. Verify read-back card displays understood details (phone, village, acres, machine, date)
//   5. Press big confirm button
//   6. See confirmed outcome with booking status
//   7. Open /desk and verify the request is recorded with the "voice booking" badge

test('Voice booking: farmer records Punjabi booking, confirms read-back, and sees badge on desk', async ({ page, context }) => {
  // Grant microphone permission to context
  await context.grantPermissions(['microphone']).catch(() => {});

  // Fallback synthetic stream if browser lacks audio device
  await page.addInitScript(() => {
    if (navigator.mediaDevices) {
      const orig = navigator.mediaDevices.getUserMedia?.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async (constraints) => {
        try {
          if (orig) return await orig(constraints);
        } catch {
          // fallback
        }
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const dst = ctx.createMediaStreamDestination();
        osc.connect(dst);
        osc.start();
        return dst.stream;
      };
    }
  });

  // 1. Open /voice
  await page.goto('/voice');
  await expect(page.locator('#voice-page')).toBeVisible({ timeout: 15000 });

  // 2. Automated assistant disclaimer and consent box
  const consentBox = page.locator('#voice-consent-box');
  await expect(consentBox).toBeVisible();
  await expect(consentBox).toContainText('ਆਟੋਮੇਟਿਡ ਬੁਕਿੰਗ ਸਿਸਟਮ');
  await expect(consentBox).toContainText('automated booking assistant');

  // Accept consent
  await page.locator('#voice-consent-btn').click();

  // 3. Mic button appears
  const micBtn = page.locator('#voice-mic-btn');
  await expect(micBtn).toBeVisible({ timeout: 10000 });

  // Start recording
  await micBtn.click();
  await expect(micBtn).toHaveClass(/recording/);

  // Wait 1 second for audio accumulation, then stop recording
  await page.waitForTimeout(1000);
  await micBtn.click();

  // 4. Read-back verification card appears
  const confirmCard = page.locator('#voice-confirm-card');
  await expect(confirmCard).toBeVisible({ timeout: 15000 });

  // Verify understood fields
  await expect(page.locator('#summary-phone')).toContainText('9876543210');
  await expect(page.locator('#summary-village')).toContainText('Rampur');
  await expect(page.locator('#summary-acres')).toContainText('2.5');
  await expect(page.locator('#summary-machine')).toContainText('Super Seeder');

  // 5. Confirm booking via button
  await page.locator('#voice-confirm-yes').click();

  // 6. Success box appears
  const successBox = page.locator('#voice-success-box');
  await expect(successBox).toBeVisible({ timeout: 15000 });
  await expect(successBox).toContainText('ਬੁਕਿੰਗ ਪੱਕੀ ਹੋ ਗਈ ਹੈ');

  // 7. Verify request on /desk with "voice booking" badge
  await page.goto('/desk');

  // Handle dev passcode or prod account gate
  const passcodeInput = page.locator('#passcode-input');
  if (await passcodeInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await passcodeInput.fill('change-me');
    await page.locator('#passcode-submit').click();
  }
  const loginUser = page.locator('#login-username');
  if (await loginUser.isVisible({ timeout: 2000 }).catch(() => false)) {
    await loginUser.fill('e2e-operator');
    await page.locator('#login-password').fill('e2e-operator-password-1');
    await page.locator('#login-submit').click();
  }

  await expect(page.locator('#desk-page')).toBeVisible({ timeout: 15000 });

  // Filter by voice source to locate the new booking immediately
  const sourceFilter = page.locator('#filter-source');
  if (await sourceFilter.isVisible({ timeout: 2000 }).catch(() => false)) {
    await sourceFilter.selectOption('voice');
  }

  // Verify booking row and "voice booking" badge
  const table = page.locator('#desk-requests-table');
  await expect(table).toBeVisible();
  await expect(table).toContainText('9876543210');
  await expect(table).toContainText('Rampur');

  const voiceBadge = page.locator('.contract-badge.badge-voice-booking, span:has-text("voice booking")').first();
  await expect(voiceBadge).toBeVisible();
});
