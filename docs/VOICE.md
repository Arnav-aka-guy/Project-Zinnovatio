# Voice booking (Punjabi and English)

A farmer books a machine by talking. The page asks five questions in a
natural voice, listens to the answer, says it back, and waits for a yes or
no. Open it at `/voice` (nav: **Voice booking**).

**Two languages.** The farmer picks **ਪੰਜਾਬੀ** or **English** on the start
screen, and can switch at any time with the toggle above the question (the
current question is asked again in the new language).

| | Punjabi | English |
| --- | --- | --- |
| Voice | `pa-IN-VaaniNeural` (female) / `pa-IN-OjasNeural` (male) | `en-IN-NeerjaNeural` / `en-IN-PrabhatNeural` (Indian English) |
| Speech recognition | `pa-IN` → text in Gurmukhi | `en-IN` → text in English letters |
| Shown first | Punjabi, English underneath | English, Punjabi underneath |

The engine understands both languages whichever is picked, including mixed
answers ("5 ਕਿੱਲੇ", "super seeder ਚਾਹੀਦਾ"). What gets saved is the same:
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
 VoicePlayer  ── plays /audio/pa/<clip>.mp3 (static, made once)
 useSpeechInput ── Web Speech API, lang pa-IN, up to 5 guesses
      │ texts
      ▼
 POST /api/voice/understand {step, texts, context} ──▶ app/voice/understand.py (pure)
      ◀── {ok, value, display_pa, readback:[clip ids], prompt, alternatives, partial}
 VoicePlayer plays readback, listens for ਹਾਂ / ਨਹੀਂ
 … five times, then POST /api/requests
```

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
python tasks.py voices                # both languages, female voices, ~1,580 clips, a few minutes
python tasks.py voices --lang en      # only English (or --lang pa)
python tasks.py voices --voice male   # male voices (Ojas / Prabhat)
python tasks.py voices --check        # list clips missing from the manifests
python tasks.py voices --dry-run      # show what would be made, no network
python tasks.py build-web             # copy the clips into web/dist
```

Uses Microsoft's neural voices through the free `edge-tts` package
(`requirements-voice.txt`). It needs internet once; after that the clips are
plain files in `web/public/audio/pa/` and `web/public/audio/en/` and play
offline. Only new or changed sentences are remade. Commit both folders so
every machine gets the same voices.

Clips per language (the ids are the same in both, so the engine's read-backs
work in either):

| Group | Clips | Punjabi | English |
| --- | --- | --- | --- |
| `prompt/` | 39 + 3 | questions, retries, outcomes | same sentences in English |
| `digit/` | 10 | ਜ਼ੀਰੋ … ਨੌਂ | zero … nine |
| `village/` | 9 | ਪਿੰਡ ਤਲਵੰਡੀ ਸਾਬੋ | Talwandi Sabo |
| `machine/` | 4 | ਸੁਪਰ ਸੀਡਰ … | Super Seeder … |
| `acres/` | 360 | ਸਾਢੇ ਪੰਜ ਏਕੜ | 5 and a half acres |
| `date/` | 366 | ਪੰਦਰਾਂ ਨਵੰਬਰ | 15th November |

Any other acreage is said as two clips: "ਸਵਾ" + "ਪੰਤਾਲੀ ਏਕੜ" in Punjabi,
"45 acres" + "and a quarter" in English (word order differs, so these three
pieces exist in one language only). A value off the quarter grid
(kanal/marla answers) starts with "ਲਗਭਗ" / "about".

## Changing things

- **Change a sentence:** edit `PROMPTS` in `app/voice/catalog.py` (each entry
  is `(Punjabi, English)`), run `python tasks.py voices`. Keep each line one
  breath: few commas.
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
| "This browser cannot do speech input" | Firefox, or Brave with speech off | Chrome or Edge; typing still works |
| "Speech input needs internet" | Chrome sends audio to its speech service | Type the answer; everything else works offline |
| "Voice clips not made yet" | No `web/public/audio/pa/manifest.json` | `python tasks.py voices` then `python tasks.py build-web` |

Every fallback shows on screen, and every step can be typed or tapped.

## Tests

- `tests/unit/test_voice_understand.py`: about 90 Punjabi and 50 English
  answers, plus checks that every read-back clip exists in both languages.
- `tests/unit/test_voice_clip_maker.py`: the clip maker, offline, with a stand-in for edge-tts.
- `tests/api/test_voice_api.py`: routes, auth, server clock.
- `web/e2e/voice_booking.spec.ts`: a full hands-free booking in Punjabi and
  one in English (scripted speech recognition, checks `pa-IN` / `en-IN`), and
  a typed-only booking with no clips.
