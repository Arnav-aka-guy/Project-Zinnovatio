import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Tier 0 full loop: Desk -> Driver -> Record -> Officer', async ({ page, context }) => {
  // 1. Desk: enter the passcode; counts show 28 scheduled, 7 will miss, 5 need info
  await page.goto('/desk');

  const passcodeInput = page.locator('#passcode-input');
  if (await passcodeInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await passcodeInput.fill('change-me');
    await page.locator('#passcode-submit').click();
  }

  await expect(page.locator('#desk-page')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#summary-metrics-bar')).toBeVisible();

  await expect(page.locator('.metric-scheduled .metric-num')).toHaveText('28');
  await expect(page.locator('.metric-will-miss .metric-num')).toHaveText('7');
  await expect(page.locator('.metric-needs-info .metric-num')).toHaveText('5');

  // 2. Machines tab: set Super Seeder 02 inactive; plan reflows; will-miss reason visible. Set active again.
  await page.locator('#tab-machines').click();
  await expect(page.locator('#machines-tab')).toBeVisible();

  const toggleBtnSS2 = page.locator('#btn-toggle-machine-2');
  await expect(toggleBtnSS2).toBeVisible();
  await toggleBtnSS2.click();

  await expect(page.locator('#machine-card-2 .machine-title-row .status-pill')).toHaveText('inactive');

  // Check Will Miss tab: at least one will-miss reason visible
  await page.locator('#tab-will-miss').click();
  await expect(page.locator('#will-miss-tab')).toBeVisible();

  const willMissTable = page.locator('.will-miss-table');
  await expect(willMissTable).toBeVisible();
  const willMissRows = willMissTable.locator('tbody tr');
  expect(await willMissRows.count()).toBeGreaterThan(0);
  const firstReason = willMissRows.first().locator('.reason-chip');
  await expect(firstReason).not.toBeEmpty();

  // Set Super Seeder 02 active again
  await page.locator('#tab-machines').click();
  await page.locator('#btn-toggle-machine-2').click();
  await expect(page.locator('#machine-card-2 .machine-title-row .status-pill')).toHaveText('active');

  // Run scheduler to reflow slots back
  await page.locator('#btn-run-scheduler').click();
  await expect(page.locator('#btn-run-scheduler')).toBeEnabled();

  // 3. Open the demo slot's message: Punjabi text with the service code (sent to the farmer in Vaari)
  await page.locator('#tab-requests').click();
  await expect(page.locator('#requests-tab-content')).toBeVisible();

  const demoReqRow = page.locator('#req-row-1');
  await expect(demoReqRow).toBeVisible();
  await demoReqRow.click();

  await expect(page.locator('#request-detail-panel')).toBeVisible();

  const msgBtn = page.locator('#btn-panel-message');
  await expect(msgBtn).toBeVisible();
  await msgBtn.click();

  const msgContainer = page.locator('#slot-message-container');
  await expect(msgContainer).toBeVisible();

  // The message reaches the farmer inside Vaari (their page and phone alerts), never by WhatsApp or SMS.
  await expect(page.locator('#btn-whatsapp-msg')).toHaveCount(0);
  const decodedText = (await msgContainer.locator('.message-punjabi').textContent()) || '';
  expect(decodedText).toContain('ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ');

  // Find the 4-digit service code in the Punjabi text
  const codeMatch = decodedText.match(/\b\d{4}\b/);
  expect(codeMatch).toBeTruthy();
  const serviceCode = codeMatch![0];

  // Get Super Seeder 01 driver URL from the Machines tab
  await page.locator('.panel-close-btn').click();
  await page.locator('#tab-machines').click();
  const driverLinkEl = page.locator('#machine-card-1 a[href^="/driver/"]');
  await expect(driverLinkEl).toBeVisible();
  const driverPath = (await driverLinkEl.getAttribute('href'))!;

  // 4. Driver page for Super Seeder 01: grant geolocation at demo plot; Start with fixture; Done with fixture and code
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 30.7333, longitude: 76.7794 });

  await page.goto(driverPath);
  await expect(page.locator('#driver-page')).toBeVisible({ timeout: 15000 });

  const job1 = page.locator('.driver-job-card').first();
  await expect(job1).toBeVisible();
  await job1.click();

  // Upload start photo
  const startCameraInput = page.locator('#driver-camera-input');
  await expect(startCameraInput).toBeAttached();

  const startFixture = path.resolve(__dirname, '../../tests/fixtures/start_field.jpg');
  await startCameraInput.setInputFiles(startFixture);

  // Click START
  const startBtn = page.locator('#btn-start-job');
  await expect(startBtn).toBeEnabled();
  await startBtn.click();

  // Three ticks evidence summary
  await expect(page.locator('#evidence-summary-ticks')).toBeVisible({ timeout: 15000 });

  // Continue to Completion
  const continueBtn = page.locator('#btn-continue-job');
  await expect(continueBtn).toBeVisible();
  await continueBtn.click();

  // Upload done photo
  const doneCameraInput = page.locator('#driver-camera-input-done');
  await expect(doneCameraInput).toBeAttached();

  const doneFixture = path.resolve(__dirname, '../../tests/fixtures/done_field.jpg');
  await doneCameraInput.setInputFiles(doneFixture);

  // Enter farmer code
  await page.locator('#farmer-code-input').fill(serviceCode);

  // Click DONE
  const doneBtn = page.locator('#btn-done-job');
  await expect(doneBtn).toBeEnabled();
  await doneBtn.click();

  // View Service Record link appears
  const viewRecordBtn = page.locator('#btn-view-record-link');
  await expect(viewRecordBtn).toBeVisible({ timeout: 15000 });

  // 5. Record page: timeline shows request, assignment, start, completion and outcome; Verify says it matches
  await viewRecordBtn.click();
  await expect(page.locator('#record-page')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#receipt-sheet')).toBeVisible();

  const timeline = page.locator('#record-timeline');
  await expect(timeline).toBeVisible();
  await expect(timeline).toContainText('Step 1 • Request Intake');
  await expect(timeline).toContainText('Step 2 • Machine Assignment');
  await expect(timeline).toContainText('Step 3 • Start Evidence');
  await expect(timeline).toContainText('Step 4 • Completion Evidence');
  await expect(timeline).toContainText('Step 5 • Final Service Outcome');
  await expect(timeline).toContainText('Code confirmed');

  const verifyBtn = page.locator('#btn-verify-hash');
  await expect(verifyBtn).toBeVisible();
  await verifyBtn.click();

  const verifyBanner = page.locator('#verify-result-banner');
  await expect(verifyBanner).toBeVisible({ timeout: 10000 });
  await expect(verifyBanner).toContainText('Matches: this record has not been edited since capture');

  // 6. Officer: completed moved by one
  await page.goto('/officer');
  if (await page.locator('#passcode-input').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.locator('#passcode-input').fill('change-me');
    await page.locator('#passcode-submit').click();
  }
  await expect(page.locator('#officer-page')).toBeVisible({ timeout: 15000 });

  const completedCount = page.locator('#metric-completed .metric-num');
  await expect(completedCount).toHaveText('1');
});

test('Done before Start, triggered through the API, shows the right message on the Driver page', async ({ page, request }) => {
  // Query machines via API to locate Super Seeder 01
  const res = await request.get('/api/machines', {
    headers: { 'X-Vaari-Passcode': 'change-me' },
  });
  expect(res.ok()).toBeTruthy();
  const machines = await res.json();
  const m1 = machines.find((m: { id: number; driver_path: string }) => m.id === 1);
  expect(m1).toBeTruthy();

  // Navigate to Driver page for Machine 1 (which has Job #2 still scheduled)
  await page.goto(m1.driver_path);
  await expect(page.locator('#driver-page')).toBeVisible({ timeout: 15000 });

  // Select the scheduled job
  const jobCard = page.locator('.driver-job-card.card-status-scheduled').first();
  await expect(jobCard).toBeVisible();
  const jobCardId = await jobCard.getAttribute('id');
  expect(jobCardId).toBeTruthy();
  const slotId = parseInt(jobCardId!.replace('driver-job-', ''), 10);

  await jobCard.click();

  // Verify the slot is scheduled and start button is present
  await expect(page.locator('#btn-start-job')).toBeVisible();

  // Trigger Done directly through the backend API before Start
  const directApiRes = await request.post(`/api/slots/${slotId}/done`, {
    headers: { 'X-Vaari-Passcode': 'change-me' },
  });
  expect(directApiRes.status()).toBe(409);
  const errJson = await directApiRes.json();
  expect(errJson.error_code).toBe('INVALID_TRANSITION');

  // Trigger Done through the Driver page UI's API execution
  await page.evaluate(async () => {
    const trigger = (window as unknown as { __triggerDone?: () => Promise<void> }).__triggerDone;
    if (trigger) {
      await trigger();
    }
  });

  // Verify the Driver page displays the user-facing invalid transition error message
  const errorBanner = page.locator('#driver-action-error');
  await expect(errorBanner).toBeVisible({ timeout: 5000 });
  await expect(errorBanner).toHaveText('This action is not allowed in the current state.');
});
