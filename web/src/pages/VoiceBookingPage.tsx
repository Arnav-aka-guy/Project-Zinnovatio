/**
 * Voice booking — a farmer books a machine by talking, in Punjabi, Hindi or English.
 *
 * Five questions (phone, village, acres, machine, harvest date), each read out
 * in a natural voice (Punjabi, Hindi or Indian English). The answer is heard by
 * Google Speech-to-Text through the server (Punjabi, Hindi and English at once,
 * any browser) or, without a Google key, by the browser's own recogniser. It is
 * understood by POST /api/voice/understand and read back for a yes or no.
 * Hands-free by default: after each question the mic opens by itself.
 *
 * It never gives up on a farmer: an answer it did not understand is asked again,
 * as often as needed, with kinder hints and tap-able choices after a few tries.
 * Only long silence pauses it (an empty room should not talk to itself).
 *
 * Every step can also be typed or tapped, so the page still works with the
 * mic blocked, on any browser, or with no voice clips made yet.
 */
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, createRequest, getVoiceScript, understandVoice } from '../api';
import FarmerQrInline from '../components/FarmerQrInline';
import { friendlyError } from '../errors';
import type { RequestOut } from '../types';
import { VoicePlayer } from '../voice/player';
import { useCloudSpeech } from '../voice/recorder';
import { useSpeechInput, type ListenError, type ListenOutcome } from '../voice/speech';
import type {
  PlayItem,
  VoiceAlternative,
  VoiceContext,
  VoiceLang,
  VoiceResult,
  VoiceScript,
  VoiceStepId,
} from '../voice/types';
import '../voice/voice.css';

const STEP_ORDER: VoiceStepId[] = ['phone', 'village', 'acres', 'machine', 'date'];
/** After this many answers in a row that were not understood, add a kind "speak slowly or choose" hint. */
const HINT_AFTER = 3;
/** Silent turns in a row before the page pauses (it keeps going after any wrong answer). */
const MAX_SILENT = 3;
/** Browser hiccups (aborted, network) retried by themselves before asking the farmer to tap. */
const MAX_HICCUPS = 3;
const ASK_PRELOAD = [
  'prompt/welcome', 'prompt/ask_phone', 'prompt/ask_village', 'prompt/ask_acres', 'prompt/ask_machine',
  'prompt/ask_date', 'prompt/ask_consent', 'prompt/confirm_q', 'prompt/rb_phone', 'prompt/retry_generic',
  'prompt/no_speech', 'prompt/say_again', 'prompt/confirm_unknown', 'prompt/keep_trying', 'prompt/paused',
  'digit/0', 'digit/1', 'digit/2', 'digit/3', 'digit/4', 'digit/5', 'digit/6', 'digit/7', 'digit/8', 'digit/9',
];

type Stage = VoiceStepId | 'intro' | 'consent' | 'done';
type Phase = 'idle' | 'speaking' | 'listening' | 'thinking' | 'confirm' | 'submitting';

interface Answer {
  value: string | number;
  display_pa: string;
  display_en: string;
  display_hi: string;
  readback: PlayItem[];
}
type Answers = Partial<Record<VoiceStepId, Answer>>;

/** One sentence in each language (hi falls back to pa when missing). */
interface Line {
  pa: string;
  en: string;
  hi?: string;
}

const players: Record<VoiceLang, VoicePlayer> = {
  pa: new VoicePlayer('pa'),
  hi: new VoicePlayer('hi'),
  en: new VoicePlayer('en'),
};
const SPEECH_LANG: Record<VoiceLang, string> = { pa: 'pa-IN', hi: 'hi-IN', en: 'en-IN' };
const LANG_NAME: Record<VoiceLang, string> = { pa: 'Punjabi', hi: 'Hindi', en: 'English' };
const LANG_KEY = 'vaari_voice_lang';

function savedLang(): VoiceLang {
  try {
    const v = sessionStorage.getItem(LANG_KEY);
    return v === 'en' || v === 'hi' ? v : 'pa';
  } catch {
    return 'pa';
  }
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

const MONTHS: Record<VoiceLang, string[]> = {
  pa: ['', 'ਜਨਵਰੀ', 'ਫ਼ਰਵਰੀ', 'ਮਾਰਚ', 'ਅਪ੍ਰੈਲ', 'ਮਈ', 'ਜੂਨ', 'ਜੁਲਾਈ', 'ਅਗਸਤ', 'ਸਤੰਬਰ', 'ਅਕਤੂਬਰ', 'ਨਵੰਬਰ', 'ਦਸੰਬਰ'],
  hi: ['', 'जनवरी', 'फ़रवरी', 'मार्च', 'अप्रैल', 'मई', 'जून', 'जुलाई', 'अगस्त', 'सितंबर', 'अक्टूबर', 'नवंबर', 'दिसंबर'],
  en: ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
};

function sayDate(iso: string, lang: VoiceLang): string {
  const [, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS[lang][m]}`;
}

/** Fixed screen text: the local language (Punjabi or Hindi) and English, side by side. */
const UI = {
  loading: { pa: 'ਲੋਡ ਹੋ ਰਿਹਾ ਹੈ…', hi: 'लोड हो रहा है…', en: 'Loading…' },
  typeInstead: { pa: '⌨️ ਕੀਬੋਰਡ ਨਾਲ ਫ਼ਾਰਮ ਭਰੋ', hi: '⌨️ कीबोर्ड से फ़ॉर्म भरें', en: 'Type your booking instead →' },
  noVoices: { pa: 'ਆਵਾਜ਼ਾਂ ਹਾਲੇ ਨਹੀਂ ਬਣੀਆਂ', hi: 'आवाज़ें अभी नहीं बनीं', en: 'Voice clips not made yet.' },
  micAllow: { pa: 'ਮਾਈਕ੍ਰੋਫ਼ੋਨ ਦੀ ਇਜਾਜ਼ਤ ਦਿਓ', hi: 'माइक्रोफ़ोन की इजाज़त दीजिए', en: 'Microphone permission required' },
  micStep1: { pa: 'ਐਡਰੈੱਸ ਬਾਰ ਵਿੱਚ ਖੱਬੇ ਪਾਸੇ 🔒 / ⚙️ ਆਈਕਨ ਦਬਾਓ।', hi: 'एड्रेस बार में बाईं ओर 🔒 / ⚙️ आइकन दबाइए।', en: 'Click the icon left of the address.' },
  micStep2: { pa: 'Microphone → Allow ਕਰੋ।', hi: 'Microphone → Allow कीजिए।', en: 'This page turns the mic on by itself once allowed. No reload needed.' },
  micRetry: { pa: '🔄 ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ', hi: '🔄 फिर कोशिश कीजिए', en: 'Try microphone again' },
  introTitle: { pa: 'ਬੋਲ ਕੇ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਬੁੱਕ ਕਰੋ', hi: 'बोलकर मशीन की बारी बुक कीजिए', en: 'Book a machine turn by speaking' },
  introSub: {
    pa: 'ਪੰਜਾਬੀ, ਹਿੰਦੀ ਜਾਂ English ਵਿੱਚ ਬੋਲੋ। ਪੰਜ ਛੋਟੇ ਸਵਾਲ।',
    hi: 'पंजाबी, हिंदी या English में बोलिए। पाँच छोटे सवाल।',
    en: 'Speak in Punjabi, Hindi or English. Five short questions.',
  },
  handsFree: { pa: 'ਹੱਥ-ਮੁਕਤ', hi: 'बिना हाथ लगाए', en: 'Hands-free' },
  listenAgain: { pa: '🔊 ਸਵਾਲ ਸੁਣੋ', hi: '🔊 सवाल सुनिए', en: 'Listen again' },
  youSaid: { pa: 'ਤੁਸੀਂ ਕਿਹਾ', hi: 'आपने कहा', en: 'You said' },
  isCorrect: { pa: 'ਕੀ ਇਹ ਠੀਕ ਹੈ ਜੀ?', hi: 'क्या यह सही है जी?', en: 'Is this correct?' },
  yes: { pa: '✓ ਹਾਂ ਜੀ', hi: '✓ हाँ जी', en: 'Yes' },
  no: { pa: '✗ ਨਹੀਂ', hi: '✗ नहीं', en: 'No' },
  saving: { pa: 'ਸੇਵ ਹੋ ਰਿਹਾ ਹੈ…', hi: 'सेव हो रहा है…', en: 'Saving…' },
  confirmBooking: { pa: '✓ ਬੁਕਿੰਗ ਪੱਕੀ ਕਰੋ', hi: '✓ बुकिंग पक्की कीजिए', en: 'Confirm booking' },
  notNow: { pa: '✗ ਹਾਲੇ ਨਹੀਂ', hi: '✗ अभी नहीं', en: 'Not now' },
  soFar: { pa: 'ਹੁਣ ਤੱਕ', hi: 'अब तक', en: 'So far' },
  listening: { pa: 'ਸੁਣ ਰਿਹਾ ਹਾਂ… ਬੋਲੋ ਜੀ', hi: 'सुन रहा हूँ… बोलिए जी', en: 'Listening… speak now' },
  sending: { pa: 'ਸਮਝ ਰਿਹਾ ਹਾਂ…', hi: 'समझ रहा हूँ…', en: 'Understanding…' },
  tapToSpeak: { pa: 'ਬੋਲਣ ਲਈ ਮਾਈਕ ਦਬਾਓ', hi: 'बोलने के लिए माइक दबाइए', en: 'Tap the mic to speak' },
  anyLanguage: {
    pa: 'ਪੰਜਾਬੀ, ਹਿੰਦੀ ਜਾਂ English, ਕਿਸੇ ਵਿੱਚ ਵੀ ਬੋਲੋ',
    hi: 'पंजाबी, हिंदी या English, किसी में भी बोलिए',
    en: 'Punjabi, Hindi or English, any of them',
  },
  heard: { pa: 'ਸੁਣਿਆ', hi: 'सुना', en: 'Heard' },
  viaTranslate: { pa: 'Google ਅਨੁਵਾਦ ਨਾਲ ਸਮਝਿਆ', hi: 'Google अनुवाद से समझा', en: 'Understood with Google Translate' },
  today: { pa: 'ਅੱਜ', hi: 'आज', en: 'Today' },
  yesterday: { pa: 'ਬੀਤਿਆ ਕੱਲ੍ਹ', hi: 'बीता हुआ कल', en: 'Yesterday' },
  tomorrow: { pa: 'ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ', hi: 'आने वाला कल', en: 'Tomorrow' },
  notKnown: { pa: 'ਹਾਲੇ ਪਤਾ ਨਹੀਂ', hi: 'अभी पता नहीं', en: 'Not known yet' },
  orType: { pa: '⌨️ ਜਾਂ ਇੱਥੇ ਲਿਖ ਕੇ ਜਵਾਬ ਦਿਓ', hi: '⌨️ या यहाँ लिखकर जवाब दीजिए', en: 'Or type your reply:' },
  send: { pa: 'ਭੇਜੋ', hi: 'भेजिए', en: 'Send ↵' },
  hearAgain: { pa: '🔊 ਦੁਬਾਰਾ ਸੁਣੋ', hi: '🔊 फिर से सुनिए', en: 'Hear again' },
  newBooking: { pa: '➕ ਨਵੀਂ ਬੁਕਿੰਗ', hi: '➕ नई बुकिंग', en: 'New booking' },
  speechGoogle: { pa: 'ਬੋਲੀ: Google', hi: 'बोली: Google', en: 'Speech: Google Cloud' },
  speechBrowser: { pa: 'ਬੋਲੀ: ਬ੍ਰਾਊਜ਼ਰ', hi: 'बोली: ब्राउज़र', en: 'Speech: this browser' },
  cloudFallback: {
    pa: 'Google ਦੀ ਬੋਲੀ ਪਛਾਣ ਜਵਾਬ ਨਹੀਂ ਦੇ ਰਹੀ। ਹੁਣ ਇਸ ਬ੍ਰਾਊਜ਼ਰ ਦੀ ਵਰਤ ਰਹੇ ਹਾਂ।',
    hi: 'Google की बोली पहचान जवाब नहीं दे रही। अब इस ब्राउज़र की इस्तेमाल कर रहे हैं।',
    en: 'Google speech-to-text is not answering. Using this browser’s speech recognition now.',
  },
  cloudDownType: {
    pa: 'Google ਦੀ ਬੋਲੀ ਪਛਾਣ ਜਵਾਬ ਨਹੀਂ ਦੇ ਰਹੀ। ਹੇਠਾਂ ਲਿਖ ਕੇ ਜਾਂ ਚੁਣ ਕੇ ਜਵਾਬ ਦਿਓ।',
    hi: 'Google की बोली पहचान जवाब नहीं दे रही। नीचे लिखकर या चुनकर जवाब दीजिए।',
    en: 'Google speech-to-text is not answering. Type or tap your answer below.',
  },
  paused: {
    pa: 'ਰੁਕਿਆ ਹੋਇਆ ਹੈ। ਤਿਆਰ ਹੋ ਕੇ ਮਾਈਕ ਦਬਾਓ।',
    hi: 'रुका हुआ है। तैयार होकर माइक दबाइए।',
    en: 'Paused. Tap the mic when you are ready.',
  },
} satisfies Record<string, { pa: string; hi: string; en: string }>;
type UIKey = keyof typeof UI;

const LISTEN_ERROR_TEXT: Record<ListenError, { pa: string; hi: string; en: string }> = {
  NOT_SUPPORTED: { pa: 'ਇਸ ਬ੍ਰਾਊਜ਼ਰ ਵਿੱਚ ਬੋਲ ਕੇ ਲਿਖਣਾ ਨਹੀਂ ਚੱਲਦਾ। ਹੇਠਾਂ ਲਿਖੋ।', hi: 'इस ब्राउज़र में बोलकर लिखना नहीं चलता। नीचे लिखिए।', en: 'This browser cannot do speech input. Use Chrome or Edge, or type below.' },
  INSECURE: { pa: 'ਮਾਈਕ ਸਿਰਫ਼ localhost ਜਾਂ https ਲਿੰਕ ਤੇ ਚੱਲਦਾ ਹੈ।', hi: 'माइक सिर्फ़ localhost या https लिंक पर चलता है।', en: 'The mic only works on localhost or an https link. Open http://localhost:8000/voice on this computer, or use the tunnel link.' },
  MIC_DENIED: { pa: 'ਮਾਈਕ ਦੀ ਇਜਾਜ਼ਤ ਬੰਦ ਹੈ।', hi: 'माइक की इजाज़त बंद है।', en: 'Microphone permission is blocked.' },
  NO_MIC: { pa: 'ਕੋਈ ਮਾਈਕ ਨਹੀਂ ਮਿਲਿਆ।', hi: 'कोई माइक नहीं मिला।', en: 'No microphone found. Plug one in or type below.' },
  NO_SPEECH: { pa: 'ਕੋਈ ਆਵਾਜ਼ ਨਹੀਂ ਆਈ।', hi: 'कोई आवाज़ नहीं आई।', en: 'Heard nothing. Tap the mic and speak.' },
  NETWORK: { pa: 'ਬੋਲੀ ਪਛਾਣ ਲਈ ਇੰਟਰਨੈੱਟ ਚਾਹੀਦਾ ਹੈ।', hi: 'बोली पहचान के लिए इंटरनेट चाहिए।', en: 'Speech input needs internet. Type below for now.' },
  ABORTED: { pa: 'ਸੁਣਨਾ ਰੁਕ ਗਿਆ।', hi: 'सुनना रुक गया।', en: 'Listening stopped.' },
  CLOUD_DOWN: { pa: 'Google ਬੋਲੀ ਪਛਾਣ ਜਵਾਬ ਨਹੀਂ ਦੇ ਰਹੀ।', hi: 'Google बोली पहचान जवाब नहीं दे रही।', en: 'Google speech-to-text is not answering.' },
  UNKNOWN: { pa: 'ਮਾਈਕ ਵਿੱਚ ਕੋਈ ਗੜਬੜ ਹੈ।', hi: 'माइक में कोई गड़बड़ है।', en: 'Something went wrong with the mic. Try again or type below.' },
};

function nextStage(answers: Answers): Stage {
  return STEP_ORDER.find(s => !answers[s]) ?? 'consent';
}

function dateClip(iso: string): string {
  const [, m, d] = iso.split('-');
  return `date/${m}-${d}`;
}

/** Speak a sentence with the device's own voice (used when a voice clip is missing). */
function speakWithDevice(text: string, bcp47: string): Promise<boolean> {
  const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined;
  if (!synth || !text.trim()) return Promise.resolve(false);
  const voices = synth.getVoices();
  const base = bcp47.slice(0, 2);
  // Only with a real voice for this language: no voice means silence plus the text on screen.
  const voice = voices.find(v => v.lang === bcp47) ?? voices.find(v => v.lang.replace('_', '-').startsWith(base));
  if (!voice) return Promise.resolve(false);
  return new Promise(resolve => {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = bcp47;
    if (voice) u.voice = voice;
    u.rate = 0.95;
    const timer = setTimeout(() => resolve(true), Math.min(20000, 1500 + text.length * 90));
    u.onend = () => {
      clearTimeout(timer);
      resolve(true);
    };
    u.onerror = () => {
      clearTimeout(timer);
      resolve(false);
    };
    synth.cancel();
    synth.speak(u);
  });
}

export default function VoiceBookingPage() {
  const [script, setScript] = useState<VoiceScript | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [stage, setStageState] = useState<Stage>('intro');
  const [phase, setPhase] = useState<Phase>('idle');
  const [answers, setAnswersState] = useState<Answers>({});
  const [pending, setPendingState] = useState<VoiceResult | null>(null);
  const [problem, setProblem] = useState<VoiceResult | null>(null);
  const [listenError, setListenError] = useState<ListenError | null>(null);
  const [heard, setHeard] = useState('');
  const [typed, setTyped] = useState('');
  const [handsFree, setHandsFree] = useState(true);
  const [subtitle, setSubtitle] = useState<Line | null>(null);
  const [outcome, setOutcome] = useState<{ req: RequestOut; items: PlayItem[]; line: Line } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [lang, setLangState] = useState<VoiceLang>(savedLang);
  const langRef = useRef<VoiceLang>(lang);
  // 'google' when the server has a Google key; switches to 'browser' for the session if Google stops answering.
  const [provider, setProviderState] = useState<'google' | 'browser'>('browser');
  const providerRef = useRef<'google' | 'browser'>('browser');

  const browserSpeech = useSpeechInput(SPEECH_LANG[lang]);
  const cloudSpeech = useCloudSpeech();
  const speech = provider === 'google' ? cloudSpeech : browserSpeech;
  useSyncExternalStore(
    useCallback(fn => {
      const subs = Object.values(players).map(p => p.subscribe(fn));
      return () => subs.forEach(u => u());
    }, []),
    () => Object.values(players).map(p => `${p.status}:${p.missing.size}`).join('|'),
  );
  const player = players[lang];
  /** The player for the language in use right now (for async code). */
  const P = () => players[langRef.current];

  /** Line in the language in use; `other` gives the second line (English, or Punjabi in English mode). */
  const pick = (l: Line | null | undefined, other = false): string => {
    if (!l) return '';
    if (other) return lang === 'en' ? l.pa : l.en;
    return lang === 'en' ? l.en : lang === 'hi' ? (l.hi ?? l.pa) : l.pa;
  };
  /** Fixed text as "local / English" (Punjabi or Hindi first, as on every screen). */
  const ui = (k: UIKey) => (lang === 'hi' ? UI[k].hi : UI[k].pa);
  const uiEn = (k: UIKey) => UI[k].en;
  const both = (k: UIKey) => `${ui(k)} / ${uiEn(k)}`;
  const display = (v: { display_pa: string; display_en: string; display_hi?: string } | undefined | null, other = false) => {
    if (!v) return '';
    if (other) return lang === 'en' ? v.display_pa : v.display_en;
    return lang === 'en' ? v.display_en : lang === 'hi' ? v.display_hi || v.display_pa : v.display_pa;
  };

  // Flow state the async conversation reads; React state mirrors it for rendering.
  const run = useRef(0);
  const flow = useRef({
    stage: 'intro' as Stage,
    answers: {} as Answers,
    pending: null as VoiceResult | null,
    partialPhone: '',
    pendingKal: false,
    tries: 0, // answers in a row that were not understood
    silent: 0, // silent turns in a row
    hiccups: 0, // browser errors in a row
    welcomed: false,
  });
  const scriptRef = useRef<VoiceScript | null>(null);
  const handsFreeRef = useRef(true);
  const speechRef = useRef({ browser: browserSpeech, cloud: cloudSpeech });
  useEffect(() => {
    speechRef.current = { browser: browserSpeech, cloud: cloudSpeech };
  });
  const activeSpeech = () => (providerRef.current === 'google' ? speechRef.current.cloud : speechRef.current.browser);

  const setProvider = (p: 'google' | 'browser') => {
    providerRef.current = p;
    setProviderState(p);
  };
  const setStage = (s: Stage) => {
    flow.current.stage = s;
    setStageState(s);
  };
  const setAnswers = (a: Answers) => {
    flow.current.answers = a;
    setAnswersState(a);
  };
  const setPending = (p: VoiceResult | null) => {
    flow.current.pending = p;
    setPendingState(p);
  };

  useEffect(() => {
    getVoiceScript()
      .then(s => {
        scriptRef.current = s;
        setScript(s);
        if (s.speech?.provider === 'google') setProvider('google');
      })
      .catch(err => setLoadError(err instanceof ApiError ? friendlyError(err.error_code) : 'Could not load.'));
    const first = players[langRef.current];
    void first.init().then(() => first.preload(ASK_PRELOAD));
    Object.values(players).forEach(p => void p.init());
    window.speechSynthesis?.getVoices(); // starts loading the device voices for the fallback
    const runCounter = run;
    return () => {
      runCounter.current++; // stops any conversation still running
      Object.values(players).forEach(p => p.stop());
      window.speechSynthesis?.cancel();
    };
  }, []);

  // ── Helpers ───────────────────────────────────────────────
  const promptLine = (clip: string | null | undefined): Line | null =>
    clip ? scriptRef.current?.prompts[clip] ?? null : null;

  const alive = (id: number) => id === run.current;

  const cancel = (): number => {
    run.current++;
    Object.values(players).forEach(p => p.stop());
    window.speechSynthesis?.cancel();
    speechRef.current.browser.abort();
    speechRef.current.cloud.abort();
    return run.current;
  };

  const micUsable = () => {
    const s = activeSpeech();
    return s.supported && s.secure && s.permission !== 'denied';
  };

  /** Play clips; when a clip is missing (Hindi clips not made yet, a new sentence), speak the line with the device voice. */
  const say = async (items: PlayItem[], line: Line | null, id: number): Promise<boolean> => {
    if (line) setSubtitle(line);
    setPhase('speaking');
    const pl = P();
    await pl.init();
    const missing = pl.status !== 'ready' || items.some(i => !pl.has(i.clip));
    if (missing && line) {
      const l = langRef.current;
      const text = l === 'en' ? line.en : l === 'hi' ? line.hi ?? line.pa : line.pa;
      const spoke = await speakWithDevice(text, SPEECH_LANG[l]);
      if (spoke) return alive(id);
    }
    const done = await pl.play(items);
    return done && alive(id);
  };

  /** Spoken read-back with a screen line, for the device-voice fallback. */
  const readbackLine = (res: VoiceResult): Line => {
    const q = promptLine('prompt/confirm_q');
    return {
      pa: `${res.display_pa}। ${q?.pa ?? ''}`,
      en: `${res.display_en}. ${q?.en ?? ''}`,
      hi: `${res.display_hi || res.display_pa}। ${q?.hi ?? ''}`,
    };
  };

  // ── Conversation ──────────────────────────────────────────
  const ask = async (target: Stage, id: number, withWelcome = false) => {
    const sc = scriptRef.current;
    if (!sc) return;
    setStage(target);
    setPending(null);
    setProblem(null);
    setHeard('');
    setTyped('');
    setListenError(null);
    setPaused(false);
    Object.assign(flow.current, { tries: 0, silent: 0, hiccups: 0, partialPhone: '', pendingKal: false });
    if (target === 'intro' || target === 'done') return;

    let items: PlayItem[];
    let line: Line | null;
    if (target === 'consent') {
      items = [{ clip: 'prompt/ask_consent' }];
      line = promptLine('prompt/ask_consent');
    } else {
      const info = sc.steps.find(s => s.id === target)!;
      items = [{ clip: info.ask_clip }];
      line = { pa: info.ask_pa, en: info.ask_en, hi: info.ask_hi };
      if (target === 'village') P().preload(sc.villages.map(v => `village/${slug(v.name)}`));
      if (target === 'machine') P().preload(sc.machines.map(m => `machine/${m.id}`));
    }
    if (withWelcome) {
      const w = promptLine('prompt/welcome');
      items = [{ clip: 'prompt/welcome', gap_ms: 380 }, ...items];
      if (w && line) line = { pa: `${w.pa} ${line.pa}`, en: `${w.en} ${line.en}`, hi: `${w.hi ?? w.pa} ${line.hi ?? line.pa}` };
    }
    if (!(await say(items, line, id))) return;
    await maybeListen(id);
  };

  const waitingPhase = (): Phase => (flow.current.pending || flow.current.stage === 'consent' ? 'confirm' : 'idle');

  const maybeListen = async (id: number) => {
    if (!handsFreeRef.current || !micUsable()) {
      setPhase(waitingPhase());
      return;
    }
    await listenNow(id);
  };

  const listenOnce = async (): Promise<ListenOutcome & { reason?: string }> => {
    const l = langRef.current;
    const step = flow.current.pending || flow.current.stage === 'consent' ? 'confirm' : (flow.current.stage as VoiceStepId);
    // Phone numbers are often said in two halves with a pause in between.
    const endSilenceMs = step === 'phone' ? 2000 : 1400;
    if (providerRef.current === 'google') return speechRef.current.cloud.listen(l, { step, endSilenceMs });
    return speechRef.current.browser.listen(SPEECH_LANG[l], { endSilenceMs });
  };

  const listenNow = async (id: number) => {
    setPaused(false);
    P().beep('listen');
    await sleep(260); // let the beep end so the mic does not hear it
    if (!alive(id)) return;
    setListenError(null);
    setPhase('listening');
    const out = await listenOnce();
    if (!alive(id)) return;
    if (!out.ok) {
      const err = out.error;
      if (err === 'CLOUD_DOWN' || (err === 'NETWORK' && providerRef.current === 'google')) {
        // Google is not answering: carry on with the browser's recogniser, or typing.
        const b = speechRef.current.browser;
        if (b.supported && b.secure) {
          setProvider('browser');
          setNotice(`${UI.cloudFallback[langRef.current]}${out.reason ? ` (${out.reason})` : ''}`);
          await listenNow(id);
        } else {
          setNotice(`${UI.cloudDownType[langRef.current]}${out.reason ? ` (${out.reason})` : ''}`);
          setListenError(err);
          setPhase(waitingPhase());
        }
        return;
      }
      if (err === 'ABORTED' || err === 'NETWORK' || err === 'UNKNOWN') {
        // Browsers sometimes stop listening on their own. Not the farmer's fault: listen again.
        flow.current.hiccups++;
        if (flow.current.hiccups <= MAX_HICCUPS) {
          await sleep(350);
          if (alive(id)) await listenNow(id);
          return;
        }
        setListenError(err);
        setPhase(waitingPhase());
        return;
      }
      setListenError(err);
      if (err === 'NO_SPEECH') {
        flow.current.silent++;
        if (flow.current.silent < MAX_SILENT) {
          if (!(await say([{ clip: 'prompt/no_speech' }], promptLine('prompt/no_speech'), id))) return;
          await listenNow(id);
          return;
        }
        // An empty room should not talk to itself forever: pause until someone taps the mic.
        await say([{ clip: 'prompt/paused' }], promptLine('prompt/paused'), id);
        if (alive(id)) {
          setPaused(true);
          setPhase(waitingPhase());
        }
        return;
      }
      if (err === 'MIC_DENIED') await say([{ clip: 'prompt/mic_off' }], promptLine('prompt/mic_off'), id);
      if (alive(id)) setPhase(waitingPhase());
      return;
    }
    Object.assign(flow.current, { silent: 0, hiccups: 0 });
    setHeard(out.texts[0]);
    await handleTexts(out.texts, id);
  };

  const handleTexts = async (texts: string[], id: number) => {
    setPhase('thinking');
    setNotice(null);
    const st = flow.current.stage;
    if (st === 'intro' || st === 'done') return;
    const confirming = !!flow.current.pending || st === 'consent';
    const step = confirming ? 'confirm' : st;
    const context: VoiceContext = {};
    if (step === 'phone' && flow.current.partialPhone) context.partial_phone = flow.current.partialPhone;
    if (step === 'date' && flow.current.pendingKal) context.pending = 'kal';
    if (step === 'confirm' && st !== 'consent') context.confirm_step = st;
    let res: VoiceResult;
    try {
      res = await understandVoice({ step, texts, context, lang: langRef.current });
    } catch (err) {
      if (!alive(id)) return;
      setNotice(err instanceof ApiError ? friendlyError(err.error_code) : 'Could not reach the server.');
      setPhase(confirming ? 'confirm' : 'idle');
      return;
    }
    if (!alive(id)) return;
    if (step === 'confirm') await onConfirm(res, id);
    else await onAnswer(res, id);
  };

  const onAnswer = async (res: VoiceResult, id: number) => {
    if (res.ok) {
      setProblem(null);
      setPending(res);
      setPhase('confirm');
      if (!(await say(res.readback, readbackLine(res), id))) return;
      flow.current.tries = 0;
      await maybeListen(id);
      return;
    }
    // Not understood: say why and listen again. Never give up; after a few tries, add a kind hint.
    flow.current.tries++;
    setProblem(res);
    if (res.partial) flow.current.partialPhone = res.partial;
    if (res.error_code === 'DATE_WHICH_KAL') flow.current.pendingKal = true;
    P().beep('error');
    const items: PlayItem[] = res.prompt ? [{ clip: res.prompt }] : [];
    let line = promptLine(res.prompt);
    if (flow.current.tries >= HINT_AFTER && !res.partial) {
      const hint = promptLine('prompt/keep_trying');
      items.push({ clip: 'prompt/keep_trying', gap_ms: 0 });
      if (line && hint) line = { pa: `${line.pa} ${hint.pa}`, en: `${line.en} ${hint.en}`, hi: `${line.hi ?? line.pa} ${hint.hi ?? hint.pa}` };
      else line = hint ?? line;
    }
    if (!(await say(items, line, id))) return;
    await maybeListen(id);
  };

  const onConfirm = async (res: VoiceResult, id: number) => {
    const st = flow.current.stage;
    if (!res.ok) {
      flow.current.tries++;
      if (!(await say([{ clip: 'prompt/confirm_unknown' }], promptLine('prompt/confirm_unknown'), id))) return;
      await maybeListen(id);
      return;
    }
    flow.current.tries = 0;
    if (st === 'consent') {
      if (res.value === true) await submit(id);
      else {
        await say([{ clip: 'prompt/booking_cancelled' }], promptLine('prompt/booking_cancelled'), id);
        if (alive(id)) setPhase('confirm');
      }
      return;
    }
    if (res.value === true) {
      await accept(id);
      return;
    }
    setPending(null);
    if (res.correction) {
      await onAnswer(res.correction, id);
      return;
    }
    Object.assign(flow.current, { partialPhone: '', pendingKal: false, tries: 0 });
    if (!(await say([{ clip: 'prompt/say_again' }], promptLine('prompt/say_again'), id))) return;
    await maybeListen(id);
  };

  const accept = async (id: number) => {
    const p = flow.current.pending;
    const st = flow.current.stage;
    if (!p || st === 'intro' || st === 'done' || st === 'consent') return;
    const next: Answers = {
      ...flow.current.answers,
      [st]: {
        value: p.value as string | number,
        display_pa: p.display_pa,
        display_en: p.display_en,
        display_hi: p.display_hi,
        readback: p.readback,
      },
    };
    setAnswers(next);
    setPending(null);
    P().beep('ok');
    await ask(nextStage(next), id);
  };

  const outcomeSpeech = (req: RequestOut): { items: PlayItem[]; line: Line } => {
    const p = (k: string) => promptLine(`prompt/${k}`) ?? { pa: '', en: '', hi: '' };
    if (req.status === 'scheduled' && req.slot) {
      const d = req.slot.service_date;
      const pre = p('done_sched_pre');
      const post = p('done_sched_post');
      return {
        items: [
          { clip: 'prompt/done_sched_pre', gap_ms: 60 },
          { clip: dateClip(d), gap_ms: 60 },
          { clip: 'prompt/done_sched_post' },
        ],
        line: {
          pa: `${pre.pa} ${sayDate(d, 'pa')} ${post.pa}`,
          en: `${pre.en} ${sayDate(d, 'en')}. ${post.en}`,
          hi: `${pre.hi ?? pre.pa} ${sayDate(d, 'hi')} ${post.hi ?? post.pa}`,
        },
      };
    }
    const key = req.status === 'will_miss' ? 'done_will_miss' : req.status === 'needs_info' ? 'done_needs_info' : 'done_open';
    return { items: [{ clip: `prompt/${key}` }], line: p(key) };
  };

  const submit = async (id: number) => {
    const a = flow.current.answers;
    if (!a.phone || !a.village || !a.acres || !a.machine || !a.date) return;
    setPhase('submitting');
    setNotice(null);
    try {
      const harvest = String(a.date.value);
      const req = await createRequest({
        phone: String(a.phone.value),
        village: String(a.village.value),
        acres: Number(a.acres.value),
        service_type: String(a.machine.value),
        harvest_date: harvest === 'not_cut_yet' ? undefined : harvest,
        consent_service: true,
        consent_evidence: true,
        consent_share: true,
      });
      if (!alive(id)) return;
      const { items, line } = outcomeSpeech(req);
      setOutcome({ req, items, line });
      setStage('done');
      await say(items, line, id);
      if (alive(id)) setPhase('idle');
    } catch (err) {
      if (!alive(id)) return;
      const ae = err instanceof ApiError ? err : null;
      setNotice(ae ? `${friendlyError(ae.error_code)} ${ae.message}` : 'Could not save the booking.');
      await say([{ clip: 'prompt/submit_failed' }], promptLine('prompt/submit_failed'), id);
      if (!alive(id)) return;
      const fieldMap: Record<string, VoiceStepId> = {
        phone: 'phone', village: 'village', acres: 'acres', service_type: 'machine', harvest_date: 'date',
      };
      const field = ae?.details?.field ? fieldMap[String(ae.details.field)] : undefined;
      if (field) {
        const rest = { ...flow.current.answers };
        delete rest[field];
        setAnswers(rest);
        await ask(field, id);
      } else {
        setPhase('confirm');
      }
    }
  };

  // ── User actions ──────────────────────────────────────────
  const switchLang = (next: VoiceLang) => {
    langRef.current = next;
    setLangState(next);
    try {
      sessionStorage.setItem(LANG_KEY, next);
    } catch {
      /* private mode */
    }
    const pl = players[next];
    void pl.init().then(() => pl.preload(ASK_PRELOAD));
  };

  /** Change language mid-booking: stop, then ask the current question again in the new language. */
  const changeLang = async (next: VoiceLang) => {
    if (next === langRef.current) return;
    const id = cancel();
    switchLang(next);
    players[next].unlock();
    const st = flow.current.stage;
    if (st !== 'intro' && st !== 'done') await ask(st, id);
  };

  const start = async (chosen?: VoiceLang) => {
    if (chosen) switchLang(chosen);
    P().unlock();
    const id = cancel();
    const s = activeSpeech();
    if (s.supported && s.secure && s.permission !== 'granted' && s.permission !== 'denied') {
      await s.requestPermission();
      if (!alive(id)) return;
    }
    const first = !flow.current.welcomed;
    flow.current.welcomed = true;
    await ask(nextStage(flow.current.answers), id, first);
  };

  const tapMic = async () => {
    P().unlock();
    if (speech.listening) {
      cancel();
      setPhase(waitingPhase());
      return;
    }
    const id = cancel();
    Object.assign(flow.current, { silent: 0, hiccups: 0 });
    const s = activeSpeech();
    if (s.permission === 'prompt' || s.permission === 'unknown') {
      await s.requestPermission();
      if (!alive(id)) return;
    }
    await listenNow(id);
  };

  const sendText = async (text: string, asNewAnswer = false) => {
    const t = text.trim();
    if (!t) return;
    P().unlock();
    const id = cancel();
    if (asNewAnswer) setPending(null);
    setHeard(t);
    setTyped('');
    await handleTexts([t], id);
  };

  const onTypedSubmit = (e: FormEvent) => {
    e.preventDefault();
    void sendText(typed);
  };

  const confirmButton = async (yes: boolean) => {
    P().unlock();
    const id = cancel();
    const st = flow.current.stage;
    if (st === 'consent') {
      if (yes) await submit(id);
      else {
        await say([{ clip: 'prompt/booking_cancelled' }], promptLine('prompt/booking_cancelled'), id);
        if (alive(id)) setPhase('confirm');
      }
      return;
    }
    if (yes) await accept(id);
    else {
      setPending(null);
      Object.assign(flow.current, { partialPhone: '', pendingKal: false, tries: 0 });
      if (!(await say([{ clip: 'prompt/say_again' }], promptLine('prompt/say_again'), id))) return;
      await maybeListen(id);
    }
  };

  const replay = async () => {
    P().unlock();
    const id = cancel();
    const st = flow.current.stage;
    const p = flow.current.pending;
    if (p) {
      if (await say(p.readback, readbackLine(p), id)) await maybeListen(id);
      return;
    }
    if (st === 'done' && outcome) {
      await say(outcome.items, outcome.line, id);
      if (alive(id)) setPhase('idle');
      return;
    }
    if (st !== 'intro' && st !== 'done') await ask(st, id);
  };

  const editStep = async (step: VoiceStepId) => {
    if (flow.current.stage === 'intro' || flow.current.stage === 'done') return;
    P().unlock();
    const id = cancel();
    await ask(step, id);
  };

  const restart = () => {
    cancel();
    setAnswers({});
    setPending(null);
    setProblem(null);
    setOutcome(null);
    setNotice(null);
    setSubtitle(null);
    setPaused(false);
    setPhase('idle');
    setStage('intro');
  };

  const toggleHandsFree = () => {
    handsFreeRef.current = !handsFreeRef.current;
    setHandsFree(handsFreeRef.current);
  };

  // ── Render ────────────────────────────────────────────────
  if (loadError) {
    return (
      <div className="vb-page">
        <div className="vb-banner vb-banner-danger">{loadError}</div>
      </div>
    );
  }
  if (!script) {
    return (
      <div className="vb-page">
        <div className="vb-card vb-center">{both('loading')}</div>
      </div>
    );
  }

  const stepInfo = STEP_ORDER.includes(stage as VoiceStepId) ? script.steps.find(s => s.id === stage) : undefined;
  const micBlocked = speech.permission === 'denied';
  const showMic = stage !== 'intro' && stage !== 'done';
  const activeStep = stage as VoiceStepId;
  const cloud = provider === 'google';
  const sending = cloud && cloudSpeech.sending;
  const altText = (alt: VoiceAlternative) => display(alt);
  const stepTitle = (s: { title_pa: string; title_hi: string }) => (lang === 'hi' ? s.title_hi : s.title_pa);
  const hint = (s: { hint_pa: string; hint_en: string; hint_hi: string }) =>
    `${lang === 'hi' ? s.hint_hi : s.hint_pa} — ${s.hint_en}`;

  return (
    <div className="vb-page" lang={lang === 'en' ? 'en' : lang}>
      <Link to="/desk" className="vb-type-link">
        {ui('typeInstead')} / {uiEn('typeInstead')}
      </Link>

      {/* Visible fallbacks */}
      {player.status === 'no-voices' && (
        <div className="vb-banner vb-banner-warning" role="status">
          🔇 <b>{both('noVoices')}</b> Questions are shown as text{window.speechSynthesis ? ' and spoken by this device' : ''}.
          Run <code>python tasks.py voices{lang === 'hi' ? ' --lang hi' : ''}</code> once, then rebuild.
        </div>
      )}
      {player.status === 'ready' && player.missing.size > 0 && (
        <div className="vb-banner vb-banner-warning" role="status">
          🔈 {player.missing.size} clip(s) missing, spoken by this device or shown as text. Run{' '}
          <code>python tasks.py voices</code>.
        </div>
      )}
      {!speech.secure && (
        <div className="vb-banner vb-banner-danger" role="alert">
          🔒 <b>{LISTEN_ERROR_TEXT.INSECURE[lang === 'hi' ? 'hi' : 'pa']}</b> {LISTEN_ERROR_TEXT.INSECURE.en}
        </div>
      )}
      {speech.secure && !speech.supported && (
        <div className="vb-banner vb-banner-warning" role="status">
          {LISTEN_ERROR_TEXT.NOT_SUPPORTED[lang === 'hi' ? 'hi' : 'pa']} <br /> {LISTEN_ERROR_TEXT.NOT_SUPPORTED.en}
        </div>
      )}
      {speech.secure && speech.supported && micBlocked && (
        <div className="vb-banner vb-banner-danger" role="alert">
          <div className="vb-banner-title">🔒 {both('micAllow')}</div>
          <ol>
            <li>
              {ui('micStep1')} <b>{window.location.host}</b> <span className="vb-en">{uiEn('micStep1')}</span>
            </li>
            <li>
              <b>{ui('micStep2')}</b> <span className="vb-en">{uiEn('micStep2')}</span>
            </li>
          </ol>
          <button type="button" className="vb-btn vb-btn-danger" onClick={() => void speech.requestPermission()}>
            {both('micRetry')}
          </button>
        </div>
      )}
      {notice && <div className="vb-banner vb-banner-danger" role="alert">{notice}</div>}

      {/* Steps */}
      <ol className="vb-steps" aria-label="Booking steps">
        {script.steps.map((s, i) => {
          const a = answers[s.id];
          const active = stage === s.id;
          return (
            <li key={s.id}>
              <button
                type="button"
                className={`vb-step ${active ? 'is-active' : ''} ${a ? 'is-done' : ''}`}
                onClick={() => void editStep(s.id)}
                disabled={stage === 'intro' || stage === 'done'}
                aria-current={active ? 'step' : undefined}
              >
                <span className="vb-step-num">{a ? '✓' : i + 1}</span>
                <span className="vb-step-text">
                  <span>
                    {stepTitle(s)} <span className="vb-en">{s.title_en}</span>
                  </span>
                  {a && <span className="vb-step-value">{display(a)}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      {stage === 'intro' && (
        <div className="vb-card vb-center vb-intro">
          <div className="vb-intro-mark" aria-hidden>🌾</div>
          <h1 className="vb-question">{UI.introTitle.pa}</h1>
          <p className="vb-sub">
            {UI.introTitle.hi} · {UI.introTitle.en}. {UI.introSub.en}
          </p>
          <div className="vb-row vb-wrap">
            <button type="button" className="vb-btn vb-btn-primary vb-btn-xl" onClick={() => void start('pa')}>
              ▶ ਪੰਜਾਬੀ ਵਿੱਚ ਸ਼ੁਰੂ ਕਰੋ
            </button>
            <button type="button" className="vb-btn vb-btn-primary vb-btn-xl" id="vb-start-hi" onClick={() => void start('hi')}>
              ▶ हिंदी में शुरू करें
            </button>
            <button type="button" className="vb-btn vb-btn-outline vb-btn-xl" onClick={() => void start('en')}>
              ▶ Start in English
            </button>
          </div>
          <p className="vb-credit">
            {cloud ? UI.speechGoogle.en : UI.speechBrowser.en} · {UI.anyLanguage.en}
            {[players.pa.voiceName, players.hi.voiceName, players.en.voiceName].some(Boolean) &&
              ` · Voices: ${[players.pa.voiceName, players.hi.voiceName, players.en.voiceName].filter(Boolean).join(' · ')}`}
          </p>
        </div>
      )}

      {(stepInfo || stage === 'consent') && (
        <div className={`vb-card vb-ask ${phase === 'listening' ? 'is-listening' : ''}`}>
          <div className="vb-status">
            <StatusPill phase={phase} lang={lang} />
            <div className="vb-lang" role="group" aria-label="Language">
              {script.languages.map(l => (
                <button
                  key={l.id}
                  type="button"
                  className={`vb-lang-btn ${lang === l.id ? 'is-on' : ''}`}
                  aria-pressed={lang === l.id}
                  onClick={() => void changeLang(l.id)}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <label className="vb-handsfree">
              <input type="checkbox" checked={handsFree} onChange={toggleHandsFree} /> {both('handsFree')}
            </label>
          </div>

          {stage === 'consent' ? (
            <>
              <h2 className="vb-question">{pick(script.prompts['prompt/ask_consent'])}</h2>
              <p className="vb-sub">{pick(script.prompts['prompt/ask_consent'], true)}</p>
              <dl className="vb-summary">
                {script.steps.map(s => (
                  <div key={s.id}>
                    <dt>
                      {stepTitle(s)} / {s.title_en}
                    </dt>
                    <dd>{display(answers[s.id])}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <>
              <h2 className="vb-question">{pick({ pa: stepInfo!.ask_pa, en: stepInfo!.ask_en, hi: stepInfo!.ask_hi })}</h2>
              <p className="vb-sub">{pick({ pa: stepInfo!.ask_pa, en: stepInfo!.ask_en, hi: stepInfo!.ask_hi }, true)}</p>
            </>
          )}

          <button type="button" className="vb-btn vb-btn-outline" onClick={() => void replay()}>
            {both('listenAgain')}
          </button>

          {subtitle && phase === 'speaking' && (
            <p className="vb-subtitle" aria-live="polite">
              {pick(subtitle)}
            </p>
          )}

          {/* Read-back waiting for yes/no */}
          {pending && stage !== 'consent' && (
            <div className="vb-confirm" aria-live="polite">
              <div className="vb-confirm-label">{both('youSaid')}</div>
              <div className="vb-confirm-value">{display(pending)}</div>
              {display(pending, true) !== display(pending) && <div className="vb-en">{display(pending, true)}</div>}
              {pending.via === 'translate' && <div className="vb-via">🌐 {both('viaTranslate')}</div>}
              <div className="vb-confirm-q">{both('isCorrect')}</div>
              <div className="vb-row">
                <button type="button" className="vb-btn vb-btn-primary vb-btn-lg" onClick={() => void confirmButton(true)}>
                  {both('yes')}
                </button>
                <button type="button" className="vb-btn vb-btn-light vb-btn-lg" onClick={() => void confirmButton(false)}>
                  {both('no')}
                </button>
              </div>
            </div>
          )}

          {stage === 'consent' && (
            <div className="vb-row">
              <button
                type="button"
                className="vb-btn vb-btn-primary vb-btn-lg"
                disabled={phase === 'submitting'}
                onClick={() => void confirmButton(true)}
              >
                {phase === 'submitting' ? both('saving') : both('confirmBooking')}
              </button>
              <button type="button" className="vb-btn vb-btn-light vb-btn-lg" onClick={() => void confirmButton(false)}>
                {both('notNow')}
              </button>
            </div>
          )}

          {/* Not understood: say why and offer choices */}
          {problem && !pending && (
            <div className="vb-problem" role="status">
              <div>{problem.prompt ? pick(script.prompts[problem.prompt]) : ''}</div>
              <div className="vb-en">{problem.prompt ? pick(script.prompts[problem.prompt], true) : ''}</div>
              {problem.partial && (
                <div className="vb-partial">
                  {both('soFar')}: <b>{problem.partial}</b> ({problem.partial.length}/10)
                </div>
              )}
              {problem.alternatives.length > 0 && (
                <div className="vb-row vb-wrap">
                  {problem.alternatives.map(alt => (
                    <button
                      key={alt.value}
                      type="button"
                      className="vb-btn vb-btn-choice"
                      onClick={() => void sendText(alt.value, true)}
                    >
                      {altText(alt)}
                      {display(alt, true) !== altText(alt) && <span className="vb-en"> · {display(alt, true)}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {showMic && (
            <div className="vb-mic-area">
              <button
                type="button"
                className={`vb-mic ${speech.listening ? 'is-on' : ''} ${speech.listening && speech.heardSomething ? 'is-hearing' : ''} ${paused ? 'is-paused' : ''}`}
                onClick={() => void tapMic()}
                disabled={!speech.supported || !speech.secure || micBlocked || phase === 'submitting'}
                aria-label={speech.listening ? 'Stop listening' : 'Tap to speak'}
                id="vb-mic"
              >
                <span aria-hidden>🎙️</span>
              </button>
              {cloud && speech.listening && (
                <div className="vb-level" aria-hidden>
                  <span style={{ transform: `scaleX(${Math.max(0.04, cloudSpeech.level)})` }} />
                </div>
              )}
              <div className="vb-mic-label">
                {speech.listening ? ui('listening') : sending ? ui('sending') : paused ? ui('paused') : ui('tapToSpeak')}
                <span className="vb-en">
                  {speech.listening
                    ? uiEn('listening')
                    : sending
                      ? uiEn('sending')
                      : paused
                        ? uiEn('paused')
                        : `${uiEn('tapToSpeak')}${cloud ? ` · ${uiEn('anyLanguage')}` : ` in ${LANG_NAME[lang]}`}`}
                </span>
              </div>
              <div className={`vb-provider ${cloud ? 'is-cloud' : ''}`} id="vb-provider">
                {cloud ? both('speechGoogle') : both('speechBrowser')}
              </div>
              {(speech.interim || heard) && (
                <div className="vb-heard">
                  {both('heard')}: <q>{speech.interim || heard}</q>
                </div>
              )}
              {listenError && listenError !== 'ABORTED' && (
                <div className="vb-listen-error">
                  {LISTEN_ERROR_TEXT[listenError][lang === 'hi' ? 'hi' : 'pa']}{' '}
                  <span className="vb-en">{LISTEN_ERROR_TEXT[listenError].en}</span>
                </div>
              )}
            </div>
          )}

          {/* Typed / tapped answers */}
          {stepInfo && !pending && (
            <div className="vb-typed">
              {activeStep === 'machine' && (
                <div className="vb-grid">
                  {script.machines.map(m => (
                    <button key={m.id} type="button" className="vb-btn vb-btn-choice vb-btn-lg" onClick={() => void sendText(m.id, true)}>
                      {lang === 'hi' ? m.name_hi : m.name_pa}
                      <span className="vb-en">{m.name_en}</span>
                    </button>
                  ))}
                </div>
              )}
              {activeStep === 'date' && (
                <div className="vb-row vb-wrap">
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('today', true)}>{both('today')}</button>
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('yesterday', true)}>{both('yesterday')}</button>
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('tomorrow', true)}>{both('tomorrow')}</button>
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('not yet', true)}>{both('notKnown')}</button>
                  <input
                    type="date"
                    className="vb-input vb-input-date"
                    aria-label="Harvest date"
                    onChange={e => e.target.value && void sendText(e.target.value, true)}
                  />
                </div>
              )}
              {activeStep !== 'machine' && (
                <form className="vb-form" onSubmit={onTypedSubmit}>
                  <label className="vb-form-label" htmlFor="vb-typed">
                    {both('orType')}
                  </label>
                  <div className="vb-row">
                    <input
                      id="vb-typed"
                      className="vb-input"
                      value={typed}
                      onChange={e => setTyped(e.target.value)}
                      placeholder={hint(stepInfo)}
                      inputMode={activeStep === 'phone' ? 'numeric' : activeStep === 'acres' ? 'decimal' : 'text'}
                      list={activeStep === 'village' ? 'vb-villages' : undefined}
                      autoComplete="off"
                    />
                    <button type="submit" className="vb-btn vb-btn-primary" disabled={!typed.trim()}>
                      {both('send')}
                    </button>
                  </div>
                  {activeStep === 'village' && (
                    <datalist id="vb-villages">
                      {script.villages.map(v => (
                        <option key={v.name} value={v.name}>
                          {lang === 'hi' ? v.name_hi : v.name_pa}
                        </option>
                      ))}
                    </datalist>
                  )}
                </form>
              )}
            </div>
          )}
        </div>
      )}

      {stage === 'done' && outcome && (
        <div className={`vb-card vb-center vb-done vb-done-${outcome.req.status}`}>
          <div className="vb-intro-mark" aria-hidden>{outcome.req.status === 'scheduled' ? '✅' : outcome.req.status === 'will_miss' ? '⚠️' : '📝'}</div>
          <h2 className="vb-question">{pick(outcome.line)}</h2>
          <p className="vb-sub">{pick(outcome.line, true)}</p>
          <p className="vb-ref">
            VR-{outcome.req.id}
            {outcome.req.slot && (
              <>
                {' '}· {outcome.req.slot.machine_name} · {outcome.req.slot.service_date}
              </>
            )}
          </p>
          {outcome.req.status !== 'cancelled' && <FarmerQrInline requestId={outcome.req.id} />}
          <div className="vb-row">
            <button type="button" className="vb-btn vb-btn-outline" onClick={() => void replay()}>
              {both('hearAgain')}
            </button>
            <button type="button" className="vb-btn vb-btn-primary" onClick={restart}>
              {both('newBooking')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusPill({ phase, lang }: { phase: Phase; lang: VoiceLang }) {
  const map: Record<Phase, { pa: string; hi: string; en: string }> = {
    idle: { pa: 'ਤੁਹਾਡੀ ਵਾਰੀ', hi: 'आपकी बारी', en: 'Your turn' },
    speaking: { pa: '🔊 ਬੋਲ ਰਿਹਾ ਹਾਂ', hi: '🔊 बोल रहा हूँ', en: 'Speaking' },
    listening: { pa: '🎙️ ਸੁਣ ਰਿਹਾ ਹਾਂ', hi: '🎙️ सुन रहा हूँ', en: 'Listening' },
    thinking: { pa: '… ਸਮਝ ਰਿਹਾ ਹਾਂ', hi: '… समझ रहा हूँ', en: 'Understanding' },
    confirm: { pa: 'ਹਾਂ ਜਾਂ ਨਹੀਂ?', hi: 'हाँ या नहीं?', en: 'Yes or no?' },
    submitting: { pa: 'ਸੇਵ ਹੋ ਰਿਹਾ ਹੈ', hi: 'सेव हो रहा है', en: 'Saving' },
  };
  const t = map[phase];
  return <span className={`vb-pill vb-pill-${phase}`}>{`${lang === 'hi' ? t.hi : t.pa} / ${t.en}`}</span>;
}

/** Same slug rule as app/voice/catalog.py village_slug(). */
function slug(name: string): string {
  return (
    name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '') || 'village'
  );
}
