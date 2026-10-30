import { test, expect } from '@playwright/test';

/**
 * Voice booking, hands-free, in Punjabi. The browser's speech recognition is
 * replaced with a scripted stand-in (headless Chromium has no speech service),
 * so this checks everything from "mic heard a sentence" onwards: understanding,
 * read-back, yes/no, corrections, the consent step and the saved request.
 */
const ANSWERS = [
  'ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ', // half the number...
  'ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ', // ...then the rest
  'ਹਾਂ ਜੀ',
  'ਮੇਰਾ ਪਿੰਡ ਤਲਵੰਡੀ ਸਾਬੋ',
  'ਹਾਂ',
  'ਸਾਢੇ ਪੰਜ ਕਿੱਲੇ',
  'ਹਾਂ ਜੀ',
  'ਸੀਡਰ', // which seeder?
  'ਸੁਪਰ ਸੀਡਰ',
  'ਹਾਂ',
  'ਕੱਲ੍ਹ', // yesterday or tomorrow?
  'ਬੀਤਿਆ',
  'ਨਹੀਂ ਜੀ 28 ਅਕਤੂਬਰ', // no, and here is the right date
  'ਹਾਂ ਜੀ',
  'ਹਾਂ ਜੀ ਕਰ ਦਿਓ', // consent
];

async function fakeSpeech(context: import('@playwright/test').BrowserContext, answers: string[]) {
  await context.grantPermissions(['microphone']);
  await context.addInitScript(answers => {
    (window as unknown as Record<string, unknown>).__speechLangs = [];
    let i = 0;
    class FakeRecognition {
      lang = '';
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      onspeechstart: (() => void) | null = null;
      start() {
        ((window as unknown as Record<string, unknown>).__speechLangs as string[]).push(this.lang);
        const text = answers[i++];
        setTimeout(() => {
          if (text === undefined) {
            this.onerror?.({ error: 'no-speech' });
            this.onend?.();
            return;
          }
          this.onspeechstart?.();
          const result = Object.assign([{ transcript: text, confidence: 0.9 }], { isFinal: true });
          this.onresult?.({ resultIndex: 0, results: [result] });
          this.onend?.();
        }, 120);
      }
      stop() {}
      abort() {
        this.onerror?.({ error: 'aborted' });
        this.onend?.();
      }
    }
    (window as unknown as Record<string, unknown>).webkitSpeechRecognition = FakeRecognition;
    (window as unknown as Record<string, unknown>).SpeechRecognition = FakeRecognition;
  }, answers);
}

async function openVoice(page: import('@playwright/test').Page) {
  const res = await page.goto('/voice');
  const passcodeInput = page.locator('#passcode-input');
  if (await passcodeInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await passcodeInput.fill('change-me');
    await page.locator('#passcode-submit').click();
  }
  return res;
}

test('voice booking: five Punjabi answers, read-backs and a saved request', async ({ page, context }) => {
  await fakeSpeech(context, ANSWERS);
  const res = await openVoice(page);
  // The page must be allowed to use the mic (a `microphone=()` policy silently blocks it).
  expect(res?.headers()['permissions-policy']).toContain('microphone=(self)');

  await page.getByRole('button', { name: /ਪੰਜਾਬੀ ਵਿੱਚ ਸ਼ੁਰੂ ਕਰੋ/ }).click();

  const done = page.locator('.vb-done');
  await expect(done).toBeVisible({ timeout: 40000 });
  await expect(done).toContainText('VR-');

  // Every step shows the understood value.
  const steps = page.locator('.vb-step-value');
  await expect(steps.nth(0)).toHaveText('98765 43210');
  await expect(steps.nth(1)).toHaveText('ਤਲਵੰਡੀ ਸਾਬੋ');
  await expect(steps.nth(2)).toHaveText('5.5 ਏਕੜ');
  await expect(steps.nth(3)).toHaveText('ਸੁਪਰ ਸੀਡਰ');
  await expect(steps.nth(4)).toContainText('28 ਅਕਤੂਬਰ');
  const langs = await page.evaluate(() => (window as unknown as Record<string, unknown>).__speechLangs as string[]);
  expect(new Set(langs)).toEqual(new Set(['pa-IN']));
});

test('voice booking in English: same five steps, English speech and read-backs', async ({ page, context }) => {
  await fakeSpeech(context, [
    'nine eight seven six five four three two one zero',
    'yes',
    'my village is Pind Kalan',
    'yes',
    'five and a half acres',
    'yes',
    'happy seeder',
    'yeah',
    'the 1st of November',
    'no it is 28th October', // correction in the same breath
    'yes',
    'yes go ahead', // consent
  ]);
  await openVoice(page);
  await page.getByRole('button', { name: /Start in English/ }).click();

  const done = page.locator('.vb-done');
  await expect(done).toBeVisible({ timeout: 40000 });
  await expect(done).toContainText('VR-');
  const steps = page.locator('.vb-step-value');
  await expect(steps.nth(0)).toHaveText('98765 43210');
  await expect(steps.nth(1)).toHaveText('Pind Kalan');
  await expect(steps.nth(2)).toHaveText('5.5 acres');
  await expect(steps.nth(3)).toHaveText('Happy Seeder');
  await expect(steps.nth(4)).toContainText('28 Oct');
  const langs = await page.evaluate(() => (window as unknown as Record<string, unknown>).__speechLangs as string[]);
  expect(new Set(langs)).toEqual(new Set(['en-IN']));
});

test('voice booking: typing works with no mic and no voice clips', async ({ page, context }) => {
  await context.addInitScript(() => {
    // Like Firefox: no speech recognition at all.
    (window as unknown as Record<string, unknown>).webkitSpeechRecognition = undefined;
    (window as unknown as Record<string, unknown>).SpeechRecognition = undefined;
  });
  await openVoice(page);
  await page.getByRole('button', { name: /ਪੰਜਾਬੀ ਵਿੱਚ ਸ਼ੁਰੂ ਕਰੋ/ }).click();

  const typeAndConfirm = async (text: string) => {
    await page.locator('#vb-typed').fill(text);
    await page.locator('#vb-typed').press('Enter');
    await page.getByRole('button', { name: /ਹਾਂ ਜੀ \/ Yes/ }).click();
  };
  await typeAndConfirm('9876501234');
  await typeAndConfirm('Pind Kalan');
  await typeAndConfirm('3');
  await page.getByRole('button', { name: /ਮਲਚਰ/ }).click();
  await page.getByRole('button', { name: /ਹਾਂ ਜੀ \/ Yes/ }).click();
  await page.getByRole('button', { name: /ਹਾਲੇ ਪਤਾ ਨਹੀਂ/ }).click();
  await page.getByRole('button', { name: /ਹਾਂ ਜੀ \/ Yes/ }).click();
  await page.getByRole('button', { name: /ਬੁਕਿੰਗ ਪੱਕੀ ਕਰੋ/ }).click();

  const done = page.locator('.vb-done');
  await expect(done).toBeVisible();
  await expect(done).toContainText('ਕਟਾਈ ਦੀ ਤਾਰੀਖ਼ ਪੱਕੀ ਹੋਣ ਤੇ'); // needs_info outcome
});
