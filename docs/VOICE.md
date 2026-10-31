# Voice booking (Punjabi, Hindi and English)

A farmer books a machine by talking. The page asks five questions in a
natural voice, listens to the answer, says it back, and waits for a yes or
no. Open it at `/voice` (nav: **Voice booking**).

**Three languages.** The farmer picks **ਪੰਜਾਬੀ**, **हिंदी** or **English** on
the start screen, and can switch at any time with the toggle above the
question (the current question is asked again in the new language).

| | Punjabi | Hindi | English |
| --- | --- | --- | --- |
| Voice | `pa-IN-VaaniNeural` / `pa-IN-OjasNeural` | `hi-IN-SwaraNeural` / `hi-IN-MadhurNeural` | `en-IN-NeerjaNeural` / `en-IN-PrabhatNeural` |
| Shown first | Punjabi, English underneath | Hindi, English underneath | English, Punjabi underneath |

**Any language, any mode.** The engine understands Punjabi, Hindi and English
whichever mode is picked, including mixed answers ("5 ਕਿੱਲੇ", "super seeder
ਚਾਹੀਦਾ", "साढ़े पाँच एकड़", "paanch acre"). Hindi in Devanagari is first written
in Gurmukhi letters (the two alphabets line up almost letter for letter,
`deva_to_guru` in `app/voice/lexicon.py`), so the Punjabi rules and the Hindi
word lists both apply.

## How answers are heard

| `VAARI_VOICE_SPEECH` | Who turns speech into text | Languages per answer | Browsers |
| --- | --- | --- | --- |
| `google` (default when `VAARI_GOOGLE_API_KEY` is set) | Google Cloud Speech-to-Text, through the server (`POST /api/voice/transcribe`) | Punjabi, Hindi and English **at once**: Google picks the one that was spoken | Every browser with a mic, iPhone included |
| `browser` (default without a key) | The browser's own recogniser (Web Speech API) | The language of the mode only (`pa-IN`, `hi-IN`, `en-IN`) | Chrome, Edge, Android |

With Google, the page records the answer itself: it measures the room noise
for a moment, waits for speech, and stops after a short silence (2 seconds
for phone numbers, which people say in two halves; 1.4 seconds otherwise).
The answer goes to the server as 16 kHz mono WAV; the server sends it to
Google with the village and machine names as hints, and the key never
reaches the browser. If Google stops answering (no internet, API switched off,
quota), the page says so on screen and carries on with the browser's
recogniser, or typing.

**Google Translate as a second chance** (`VAARI_VOICE_TRANSLATE`, on when the
key is set): when the app's own rules cannot read an answer, the text is
translated to English and read again. The screen shows "Understood with
Google Translate". Phone numbers are never sent to Translate.

## It never gives up

- An answer it did not understand is asked again, as often as needed. After
  three in a row it adds "No problem. Speak slowly and clearly, or choose
  below." and the choices (villages, machines, dates) are on screen.
- When the browser stops listening by itself (Chrome sometimes does), it
  listens again without fuss.
- Only silence pauses it: after three silent turns in a row it says "I have
  paused. Tap the mic when you are ready." and the mic button pulses.
- The browser recogniser now listens continuously and ends the answer after a
  short silence, instead of at the first breath. What gets saved is the same:
phone digits, the village's name from the village list, acres as a number,
the machine id and an ISO date.

| Step | Question (spoken) | Examples it understands |
| --- | --- | --- |
| 1. ਫ਼ੋਨ Phone | ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਦਸ ਅੰਕਾਂ ਦਾ ਮੋਬਾਈਲ ਨੰਬਰ ਦੱਸੋ ਜੀ। | "ਨੌਂ ਅੱਠ ਸੱਤ…", "98765 43210", "+91…", Gurmukhi digits, "ਅਠਾਨਵੇਂ…" (pairs), "double 7", the number said in two goes |
| 2. ਪਿੰਡ Village | ਤੁਹਾਡਾ ਖੇਤ ਕਿਹੜੇ ਪਿੰਡ ਵਿੱਚ ਹੈ ਜੀ? | "ਮੇਰਾ ਪਿੰਡ ਤਲਵੰਡੀ ਸਾਬੋ ਹੈ", "ਮੋੜ ਮੰਡੀ", "Talwandi Sabo", short names ("ਸੰਗਤ") |
| 3. ਏਕੜ Acres | ਕਿੰਨੇ ਏਕੜ ਵਿੱਚ ਕੰਮ ਕਰਵਾਉਣਾ ਹੈ ਜੀ? | "ਸਾਢੇ ਪੰਜ", "ਪੌਣੇ ਚਾਰ ਕਿੱਲੇ", "ਡੇਢ", "ਢਾਈ", "5 ਕਿੱਲੇ 4 ਕਨਾਲ", "ਇੱਕ ਹੈਕਟੇਅਰ", "2,5" |
| 4. ਮਸ਼ੀਨ Machine | ਤੁਹਾਨੂੰ ਕਿਹੜੀ ਮਸ਼ੀਨ ਚਾਹੀਦੀ ਹੈ ਜੀ? | "ਸੁਪਰ ਸੀਡਰ", "ਹੈਪੀ", "ਬੇਲਰ", "ਪਰਾਲੀ ਦੀਆਂ ਗੱਠਾਂ", "ਮਲਚਰ"; just "ਸੀਡਰ" → asks which one |
| 5. ਤਾਰੀਖ਼ Date | ਝੋਨੇ ਦੀ ਕਟਾਈ ਕਦੋਂ ਹੋਈ ਹੈ ਜਾਂ ਕਦੋਂ ਹੋਣੀ ਹੈ ਜੀ? | "ਅੱਜ", "ਕੱਲ੍ਹ ਹੋਈ ਸੀ" / "ਕੱਲ੍ਹ ਕੱਟਾਂਗੇ" (tense decides), "15 ਨਵੰਬਰ", "ਪਹਿਲੀ ਨਵੰਬਰ", "3 ਦਿਨ ਪਹਿਲਾਂ", "ਅਗਲੇ ਹਫ਼ਤੇ", "ਐਤਵਾਰ", "ਦੀਵਾਲੀ ਤੋਂ ਦੋ ਦਿਨ ਬਾਅਦ", "ਪਤਾ ਨਹੀਂ" |

English examples: "nine eight seven six…", "ninety eight seventy six…",
"my village is Bhucho Khurd", "five and a half acres", "5 acres and a half",
"half an acre", "two point five", "I need a happy seeder", "super cedar"
(a common mishearing), "tomorrow", "day after tomorrow", "15th November",
"the 1st of November", "3 days ago", "in 2 days", "last Sunday",
"two days after Diwali", "not harvested yet", "yeah that's right", "no, it is
28th October".

Then a consent question, and the booking is saved with `POST /api/requests`
(source `form`). The result is spoken: scheduled date, needs-info or will-miss.

"ਕੱਲ੍ਹ" means both yesterday and tomorrow. When the sentence has no tense, the
page asks "ਬੀਤਿਆ ਕੱਲ੍ਹ ਜਾਂ ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ ਜੀ?" and shows two buttons.

## How it fits together

```
 browser                                             server
 ───────                                             ──────
 VoicePlayer  ── plays /audio/<pa|hi|en>/<clip>.mp3 (static, made once)
 useCloudSpeech ── records one answer (WAV) ── POST /api/voice/transcribe ──▶ Google Speech-to-Text
   or useSpeechInput (Web Speech API)                   (pa-Guru-IN + hi-IN + en-IN, hints)
      │ texts (up to 5 guesses)
      ▼
 POST /api/voice/understand {step, texts, context, lang} ──▶ app/voice/understand.py (pure)
                                                         └─▶ Google Translate, only if not understood
      ◀── {ok, value, display_pa/hi/en, readback:[clip ids], prompt, alternatives, partial, via}
 VoicePlayer plays readback, listens for ਹਾਂ / हाँ / yes
 … five times, then POST /api/requests
```

A clip that is missing (Hindi clips not made yet, a new sentence) is spoken
with the device's own voice when it has one for that language, and the text is
always on screen.

- `app/voice/catalog.py` holds every spoken sentence and the clip id rules.
  The clip maker and the engine both read it, so a read-back can never point
  at a clip that does not exist (a test checks every acreage and date).
- `app/voice/lexicon.py` holds the Punjabi words: numbers 0–100, fractions
  (ਸਵਾ, ਸਾਢੇ, ਪੌਣੇ, ਡੇਢ, ਢਾਈ), land units (ਕਿੱਲਾ, ਕਨਾਲ, ਮਰਲਾ), months,
  weekdays, tense words, yes/no, machine names and Gurmukhi village names.
- `app/voice/understand.py` is pure: no clock, no database. The route passes
  in `clock.today()` and the village list.
- `web/src/voice/player.ts` decodes each clip once, finds where speech starts
  and ends (10 ms windows, 30 dB below the loudest part), and plays only that
  part, back to back, with a short fade and even loudness. This is why a
  read-back stitched from many clips has no dead air.
- `web/src/voice/speech.ts` watches the mic permission live, so switching it
  to Allow fixes the page without a reload.

## Making the voices

```
python tasks.py voices                # all three languages, female voices, ~2,380 clips, a few minutes
python tasks.py voices --lang hi      # only Hindi (or --lang pa, --lang en)
python tasks.py voices --voice male   # male voices (Ojas / Prabhat)
python tasks.py voices --check        # list clips missing from the manifests
python tasks.py voices --dry-run      # show what would be made, no network
python tasks.py build-web             # copy the clips into web/dist
```

Uses Microsoft's neural voices through the free `edge-tts` package
(`requirements-voice.txt`). It needs internet once; after that the clips are
plain files in `web/public/audio/pa/`, `web/public/audio/hi/` and
`web/public/audio/en/` and play offline. Only new or changed sentences are
remade. Commit all three folders so every machine gets the same voices.

Clips per language (the ids are the same in both, so the engine's read-backs
work in either):

| Group | Clips | Punjabi | Hindi | English |
| --- | --- | --- | --- | --- |
| `prompt/` | 41 + 3 | questions, retries, outcomes | same in Hindi | same in English |
| `digit/` | 10 | ਜ਼ੀਰੋ … ਨੌਂ | शून्य … नौ | zero … nine |
| `village/` | 9 | ਪਿੰਡ ਤਲਵੰਡੀ ਸਾਬੋ | गाँव तलवंडी साबो | Talwandi Sabo |
| `machine/` | 4 | ਸੁਪਰ ਸੀਡਰ … | सुपर सीडर … | Super Seeder … |
| `acres/` | 360 | ਸਾਢੇ ਪੰਜ ਏਕੜ | साढ़े पाँच एकड़ | 5 and a half acres |
| `date/` | 366 | ਪੰਦਰਾਂ ਨਵੰਬਰ | पंद्रह नवंबर | 15th November |

Any other acreage is said as two clips: "ਸਵਾ" + "ਪੰਤਾਲੀ ਏਕੜ" in Punjabi,
"45 acres" + "and a quarter" in English (word order differs, so these three
pieces exist in one language only). A value off the quarter grid
(kanal/marla answers) starts with "ਲਗਭਗ" / "about".

## Changing things

- **Change a sentence:** edit `PROMPTS` (Punjabi, English) and `PROMPTS_HI`
  (Hindi) in `app/voice/catalog.py`, run `python tasks.py voices`. Keep each
  line one breath: few commas. A test checks both have the same keys.
- **Hindi words:** the Hindi lists are at the end of `app/voice/lexicon.py`,
  written in Devanagari and added to the Punjabi lists in their converted form.
- **Add a village's Gurmukhi name:** add a `VillageEntry` to `VILLAGES_PA` in
  `app/voice/lexicon.py` (aliases are other spellings people say), then
  `python tasks.py voices`. A village without one still matches by its English
  spelling and is read back as text only.
- **Next season's festivals:** add rows to `FESTIVALS` in `lexicon.py`.

## When it does not work

| On screen | Cause | Fix |
| --- | --- | --- |
| "Microphone permission required" even after Allow | Server sent `Permissions-Policy: microphone=()` | Fixed in `app/security_headers.py`: now `microphone=(self)` |
| "The mic only works on localhost or an https link" | Page opened as `http://192.168.x.x:8000` | Use `http://localhost:8000/voice` on that computer, or `python tasks.py tunnel` for an https link |
| "This browser cannot do speech input" | Firefox or Safari without a Google key | Set `VAARI_GOOGLE_API_KEY` (works on every browser), or use Chrome/Edge; typing still works |
| "Speech input needs internet" | Speech recognition (browser or Google) needs internet | Type the answer; everything else works offline |
| "Google speech-to-text is not answering (reason)" | Key wrong, API not turned on, quota, no internet | `python tasks.py check-google` says which, and how to fix it; meanwhile the browser recogniser is used |
| "Voice clips not made yet" | No `web/public/audio/<lang>/manifest.json` | `python tasks.py voices` then `python tasks.py build-web` |
| Status pill shows "Speech: this browser" with a key set | `VAARI_VOICE_SPEECH=browser`, or Google failed earlier in this visit | Check `.env`; reload the page |

Every fallback shows on screen, and every step can be typed or tapped.

## Setting up Google (once)

1. In Google Cloud Console, in the project that owns the key: **APIs & Services → Library**, turn on
   **Cloud Speech-to-Text API** and **Cloud Translation API**. Billing must be on for the project.
2. **Credentials → the key → API restrictions**: allow those two APIs. Do not restrict it to websites
   (HTTP referrers): the key is used by the Vaari server, not by browsers.
3. Put it in `.env` as `VAARI_GOOGLE_API_KEY=...` (never in a committed file), restart, and run
   `python tasks.py check-google`. Both lines should say OK.
4. Spoken answers are sent to Google, as the browser's own recogniser already does in Chrome.
   Translate gets only answers the rules could not read, and never phone numbers.

## Tests

- `tests/unit/test_voice_understand.py`: about 90 Punjabi and 50 English
  answers, plus checks that every read-back clip exists in both languages.
- `tests/unit/test_voice_clip_maker.py`: the clip maker, offline, with a stand-in for edge-tts.
- `tests/api/test_voice_api.py`: routes, auth, server clock.
- `web/e2e/voice_booking.spec.ts`: a full hands-free booking in Punjabi and
  one in English (scripted speech recognition, checks `pa-IN` / `en-IN`), and
  a typed-only booking with no clips.
- `tests/unit/test_voice_hindi.py`: Hindi answers in Devanagari, romanised and
  as heard by the Punjabi recogniser, in every mode; the Hindi voice script.
- `tests/api/test_voice_google.py`: the Google requests (languages, hints,
  WAV, key only on the server), failures, and the Translate second chance
  (Google mocked).
- `web/e2e/voice_hindi_cloud.spec.ts`: a Hindi booking through the Google path
  (fake microphone, real WAV recording and silence detection), wrong answers
  that never stop the conversation, a browser hiccup, the pause after silence,
  and the fallback when Google is not answering.
