import { test, expect, type BrowserContext, type Page, type Route } from '@playwright/test';

/**
 * Voice booking v0.4: Hindi, Google speech-to-text, and a conversation that never gives up.
 *
 * - Hindi end to end through the Google path: the page records the farmer (a fake microphone
 *   that "speaks" a tone for a moment each time the page listens), sends 16 kHz WAV to
 *   /api/voice/transcribe (answered here with scripted Hindi text, as Google would), and the
 *   real server understands the Hindi and saves the booking.
 * - Wrong answers never stop the conversation; a browser that stops listening on its own is
 *   restarted; long silence pauses it.
 * - When Google is not answering, the page says so and carries on with the browser's recogniser.
 */
test.use({
  launchOptions: {
    args: ['--autoplay-policy=no-user-gesture-required'],
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}),
  },
});

async function openVoice(page: Page) {
  await page.goto('/voice');
  const box = page.locator('#passcode-input');
  if (await box.isVisible({ timeout: 2000 }).catch(() => false)) {
    await box.fill('change-me');
    await page.locator('#passcode-submit').click();
  }
}

/** A microphone that says something (a tone) for 0.7 s, half a second after each time the page starts listening. */
async function fakeMicrophone(context: BrowserContext) {
  await context.grantPermissions(['microphone']);
  await context.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    navigator.mediaDevices.getUserMedia = async () => {
      const ac = new AudioContext();
      await ac.resume();
      const osc = ac.createOscillator();
      osc.frequency.value = 220;
      const gain = ac.createGain();
      gain.gain.value = 0;
      const dest = ac.createMediaStreamDestination();
      osc.connect(gain).connect(dest);
      osc.start();
      w.__fakeVoice = gain;
      return dest.stream;
    };
    const orig = AudioContext.prototype.createScriptProcessor;
    AudioContext.prototype.createScriptProcessor = function (...args: Parameters<typeof orig>) {
      const node = orig.apply(this, args);
      const gain = w.__fakeVoice as GainNode | undefined;
      w.__listens = ((w.__listens as number) ?? 0) + 1;
      if (gain) {
        setTimeout(() => {
          gain.gain.value = 0.6;
          setTimeout(() => (gain.gain.value = 0), 700);
        }, 500);
      }
      return node;
    };
  });
}

/** The browser's own recogniser, scripted. '__abort__' = the browser stops by itself; '__silence__' = nothing heard. */
async function fakeBrowserSpeech(context: BrowserContext, answers: string[]) {
  await context.grantPermissions(['microphone']);
  await context.addInitScript(answers => {
    let i = 0;
    class FakeRecognition {
      lang = '';
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      onspeechstart: (() => void) | null = null;
      start() {
        const text = answers[i++];
        setTimeout(() => {
          if (text === undefined || text === '__silence__') {
            this.onerror?.({ error: 'no-speech' });
            this.onend?.();
            return;
          }
          if (text === '__abort__') {
            this.onerror?.({ error: 'aborted' });
            this.onend?.();
            return;
          }
          this.onspeechstart?.();
          const result = Object.assign([{ transcript: text, confidence: 0.9 }], { isFinal: true });
          this.onresult?.({ resultIndex: 0, results: [result] });
          this.onend?.();
        }, 100);
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

/** Make the server's script say "use Google" (as it does when VAARI_GOOGLE_API_KEY is set). */
async function scriptSaysGoogle(page: Page) {
  await page.route('**/api/voice/script', async (route: Route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.speech = { provider: 'google', translate: false };
    await route.fulfill({ response: res, json: body });
  });
}

test('Hindi booking through Google speech-to-text, read back in Hindi', async ({ page, context }) => {
  test.setTimeout(120000);
  await fakeMicrophone(context);
  await scriptSaysGoogle(page);
  const phone = `9${String(Date.now()).slice(-9)}`;
  const hindiDigits = ['शून्य', 'एक', 'दो', 'तीन', 'चार', 'पाँच', 'छह', 'सात', 'आठ', 'नौ'];
  const answers = [
    phone.split('').map(d => hindiDigits[Number(d)]).join(' '),
    'हाँ जी',
    'तलवंडी साबो गाँव',
    'हाँ',
    'साढ़े पाँच एकड़',
    'हाँ जी',
    'मुझे हैप्पी सीडर चाहिए',
    'हाँ',
    'अभी पता नहीं',
    'हाँ जी',
    'हाँ जी कर दो',
  ];
  const sent: { lang: string; step: string; wav: boolean }[] = [];
  await page.route('**/api/voice/transcribe', async (route: Route) => {
    const body = route.request().postDataBuffer() ?? Buffer.alloc(0);
    const text = body.toString('latin1');
    sent.push({
      lang: /name="lang"\r\n\r\n(\w+)/.exec(text)?.[1] ?? '',
      step: /name="step"\r\n\r\n(\w+)/.exec(text)?.[1] ?? '',
      wav: text.includes('RIFF') && text.includes('WAVEfmt '),
    });
    const said = answers[sent.length - 1];
    await route.fulfill({ json: { texts: said ? [said] : [], language: 'hi-in', provider: 'google', error: said ? null : 'no_speech' } });
  });

  await openVoice(page);
  await page.locator('#vb-start-hi').click();
  await expect(page.locator('#vb-provider')).toContainText('Google');
  await expect(page.locator('.vb-done')).toBeVisible({ timeout: 110000 });

  const values = await page.locator('.vb-step-value').allTextContents();
  expect(values).toEqual([
    `${phone.slice(0, 5)} ${phone.slice(5)}`,
    'तलवंडी साबो',
    '5.5 एकड़',
    'हैप्पी सीडर',
    'अभी तय नहीं',
  ]);
  expect(sent.length).toBe(answers.length);
  expect(sent.every(s => s.lang === 'hi' && s.wav)).toBe(true);
  expect(sent.map(s => s.step)).toEqual([
    'phone', 'confirm', 'village', 'confirm', 'acres', 'confirm', 'machine', 'confirm', 'date', 'confirm', 'confirm',
  ]);
});

test('wrong answers never stop the conversation, and a browser hiccup is retried', async ({ page, context }) => {
  test.setTimeout(120000);
  await fakeBrowserSpeech(context, [
    'ਪਤਾ ਨਹੀਂ ਜੀ',
    '__abort__', // the browser stops listening by itself
    'ਹੈਲੋ ਹੈਲੋ',
    'ਕੀ ਕਹਿੰਦੇ ਹੋ',
    'ਰੁਕੋ ਜ਼ਰਾ',
    'ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ', // finally right
    'ਹਾਂ ਜੀ',
    '__silence__',
    '__silence__',
    '__silence__',
  ]);
  await openVoice(page);
  await page.getByRole('button', { name: /ਪੰਜਾਬੀ ਵਿੱਚ ਸ਼ੁਰੂ ਕਰੋ/ }).click();

  // Four answers it could not use, one hiccup: it kept asking and got the number in the end.
  await expect(page.locator('.vb-step-value').first()).toHaveText('98765 43210', { timeout: 90000 });
  await expect(page.locator('.vb-step.is-active')).toContainText('ਪਿੰਡ');
  // Three silent turns in a row: it pauses and waits for a tap instead of talking to an empty room.
  await expect(page.locator('#vb-mic.is-paused')).toBeVisible({ timeout: 60000 });
  await expect(page.locator('.vb-mic-label')).toContainText('Paused');
});

test('Google not answering: the page says so and carries on with the browser recogniser', async ({ page, context }) => {
  test.setTimeout(90000);
  await fakeMicrophone(context);
  await fakeBrowserSpeech(context, ['9876543210', 'ਹਾਂ ਜੀ']);
  await scriptSaysGoogle(page);
  let cloudCalls = 0;
  await page.route('**/api/voice/transcribe', async (route: Route) => {
    cloudCalls++;
    await route.fulfill({
      status: 503,
      json: { error_code: 'VOICE_CLOUD_FAILED', message: 'Google speech-to-text did not answer.', details: { reason: 'api_disabled' } },
    });
  });
  await openVoice(page);
  await page.getByRole('button', { name: /Start in English/ }).click();
  await expect(page.locator('.vb-banner-danger')).toContainText('Google speech-to-text is not answering', { timeout: 30000 });
  await expect(page.locator('.vb-banner-danger')).toContainText('api_disabled');
  await expect(page.locator('#vb-provider')).toContainText('this browser');
  await expect(page.locator('.vb-step-value').first()).toHaveText('98765 43210', { timeout: 40000 });
  expect(cloudCalls).toBe(1);
});
