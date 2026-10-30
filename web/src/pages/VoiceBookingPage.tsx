/**
 * Voice booking — a farmer books a machine by talking, in Punjabi or English.
 *
 * Five questions (phone, village, acres, machine, harvest date), each read out
 * in a natural voice (Punjabi pa-IN or Indian English en-IN). The answer is heard by the browser's speech
 * recognition, understood by POST /api/voice/understand, and read back
 * ("ਪਿੰਡ ਤਲਵੰਡੀ ਸਾਬੋ। ਕੀ ਇਹ ਠੀਕ ਹੈ ਜੀ?") for a yes or no. Hands-free by
 * default: after each question the mic opens by itself.
 *
 * Every step can also be typed or tapped, so the page still works with the
 * mic blocked, on Firefox, or with no voice clips made yet.
 */
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, createRequest, getVoiceScript, understandVoice } from '../api';
import { friendlyError } from '../errors';
import type { RequestOut } from '../types';
import { VoicePlayer } from '../voice/player';
import { useSpeechInput, type ListenError } from '../voice/speech';
import type { PlayItem, VoiceContext, VoiceLang, VoiceResult, VoiceScript, VoiceStepId } from '../voice/types';
import '../voice/voice.css';

const STEP_ORDER: VoiceStepId[] = ['phone', 'village', 'acres', 'machine', 'date'];
const MAX_AUTO_TRIES = 3;
const ASK_PRELOAD = [
  'prompt/welcome', 'prompt/ask_phone', 'prompt/ask_village', 'prompt/ask_acres', 'prompt/ask_machine',
  'prompt/ask_date', 'prompt/ask_consent', 'prompt/confirm_q', 'prompt/rb_phone', 'prompt/retry_generic',
  'prompt/no_speech', 'prompt/say_again', 'prompt/confirm_unknown',
  'digit/0', 'digit/1', 'digit/2', 'digit/3', 'digit/4', 'digit/5', 'digit/6', 'digit/7', 'digit/8', 'digit/9',
];

type Stage = VoiceStepId | 'intro' | 'consent' | 'done';
type Phase = 'idle' | 'speaking' | 'listening' | 'thinking' | 'confirm' | 'submitting';

interface Answer {
  value: string | number;
  display_pa: string;
  display_en: string;
  readback: PlayItem[];
}
type Answers = Partial<Record<VoiceStepId, Answer>>;

interface Line {
  pa: string;
  en: string;
}

const players: Record<VoiceLang, VoicePlayer> = { pa: new VoicePlayer('pa'), en: new VoicePlayer('en') };
const SPEECH_LANG: Record<VoiceLang, string> = { pa: 'pa-IN', en: 'en-IN' };
const LANG_KEY = 'vaari_voice_lang';

function savedLang(): VoiceLang {
  try {
    return sessionStorage.getItem(LANG_KEY) === 'en' ? 'en' : 'pa';
  } catch {
    return 'pa';
  }
}

const PA_MONTHS = ['', 'ਜਨਵਰੀ', 'ਫ਼ਰਵਰੀ', 'ਮਾਰਚ', 'ਅਪ੍ਰੈਲ', 'ਮਈ', 'ਜੂਨ', 'ਜੁਲਾਈ', 'ਅਗਸਤ', 'ਸਤੰਬਰ', 'ਅਕਤੂਬਰ', 'ਨਵੰਬਰ', 'ਦਸੰਬਰ'];
const EN_MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function sayDate(iso: string, lang: VoiceLang): string {
  const [, m, d] = iso.split('-').map(Number);
  return lang === 'en' ? `${d} ${EN_MONTHS[m]}` : `${d} ${PA_MONTHS[m]}`;
}

const LISTEN_ERROR_TEXT: Record<ListenError, Line> = {
  NOT_SUPPORTED: { pa: 'ਇਸ ਬ੍ਰਾਊਜ਼ਰ ਵਿੱਚ ਬੋਲ ਕੇ ਲਿਖਣਾ ਨਹੀਂ ਚੱਲਦਾ। Chrome ਜਾਂ Edge ਵਰਤੋ, ਜਾਂ ਹੇਠਾਂ ਲਿਖੋ।', en: 'This browser cannot do speech input. Use Chrome or Edge, or type below.' },
  INSECURE: { pa: 'ਮਾਈਕ ਸਿਰਫ਼ localhost ਜਾਂ https ਲਿੰਕ ਤੇ ਚੱਲਦਾ ਹੈ।', en: 'The mic only works on localhost or an https link. Open http://localhost:8000/voice on this computer, or use the tunnel link.' },
  MIC_DENIED: { pa: 'ਮਾਈਕ ਦੀ ਇਜਾਜ਼ਤ ਬੰਦ ਹੈ।', en: 'Microphone permission is blocked.' },
  NO_MIC: { pa: 'ਕੋਈ ਮਾਈਕ ਨਹੀਂ ਮਿਲਿਆ।', en: 'No microphone found. Plug one in or type below.' },
  NO_SPEECH: { pa: 'ਕੋਈ ਆਵਾਜ਼ ਨਹੀਂ ਆਈ।', en: 'Heard nothing. Tap the mic and speak.' },
  NETWORK: { pa: 'ਬੋਲੀ ਪਛਾਣ ਲਈ ਇੰਟਰਨੈੱਟ ਚਾਹੀਦਾ ਹੈ।', en: 'Speech input needs internet. Type below for now.' },
  ABORTED: { pa: 'ਸੁਣਨਾ ਰੁਕ ਗਿਆ।', en: 'Listening stopped.' },
  UNKNOWN: { pa: 'ਮਾਈਕ ਵਿੱਚ ਕੋਈ ਗੜਬੜ ਹੈ।', en: 'Something went wrong with the mic. Try again or type below.' },
};

function nextStage(answers: Answers): Stage {
  return STEP_ORDER.find(s => !answers[s]) ?? 'consent';
}

function dateClip(iso: string): string {
  const [, m, d] = iso.split('-');
  return `date/${m}-${d}`;
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
  const [lang, setLangState] = useState<VoiceLang>(savedLang);
  const langRef = useRef<VoiceLang>(lang);

  const speech = useSpeechInput(SPEECH_LANG[lang]);
  useSyncExternalStore(
    useCallback(fn => {
      const a = players.pa.subscribe(fn);
      const b = players.en.subscribe(fn);
      return () => {
        a();
        b();
      };
    }, []),
    () => `${players.pa.status}:${players.pa.missing.size}:${players.en.status}:${players.en.missing.size}`,
  );
  const player = players[lang];
  /** The player for the language in use right now (for async code). */
  const P = () => players[langRef.current];
  /** Pick the line for the current language; `other` gives the second language. */
  const pick = (l: Line | null | undefined, other = false): string => {
    if (!l) return '';
    const en = lang === 'en' ? !other : other;
    return en ? l.en : l.pa;
  };

  // Flow state the async conversation reads; React state mirrors it for rendering.
  const run = useRef(0);
  const flow = useRef({
    stage: 'intro' as Stage,
    answers: {} as Answers,
    pending: null as VoiceResult | null,
    partialPhone: '',
    pendingKal: false,
    tries: 0,
    welcomed: false,
  });
  const scriptRef = useRef<VoiceScript | null>(null);
  const handsFreeRef = useRef(true);
  const speechRef = useRef(speech);
  useEffect(() => {
    speechRef.current = speech;
  });

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
      })
      .catch(err => setLoadError(err instanceof ApiError ? friendlyError(err.error_code) : 'Could not load.'));
    const first = players[langRef.current];
    void first.init().then(() => first.preload(ASK_PRELOAD));
    void players[langRef.current === 'pa' ? 'en' : 'pa'].init();
    const runCounter = run;
    return () => {
      runCounter.current++; // stops any conversation still running
      players.pa.stop();
      players.en.stop();
    };
  }, []);

  // ── Helpers ───────────────────────────────────────────────
  const promptLine = (clip: string | null | undefined): Line | null =>
    clip ? scriptRef.current?.prompts[clip] ?? null : null;

  const alive = (id: number) => id === run.current;

  const cancel = (): number => {
    run.current++;
    players.pa.stop();
    players.en.stop();
    speechRef.current.abort();
    return run.current;
  };

  const micUsable = () => {
    const s = speechRef.current;
    return s.supported && s.secure && s.permission !== 'denied';
  };

  const say = async (items: PlayItem[], line: Line | null, id: number): Promise<boolean> => {
    if (line) setSubtitle(line);
    setPhase('speaking');
    const done = await P().play(items);
    return done && alive(id);
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
    Object.assign(flow.current, { tries: 0, partialPhone: '', pendingKal: false });
    if (target === 'intro' || target === 'done') return;

    let items: PlayItem[];
    let line: Line | null;
    if (target === 'consent') {
      items = [{ clip: 'prompt/ask_consent' }];
      line = promptLine('prompt/ask_consent');
    } else {
      const info = sc.steps.find(s => s.id === target)!;
      items = [{ clip: info.ask_clip }];
      line = { pa: info.ask_pa, en: info.ask_en };
      if (target === 'village') P().preload(sc.villages.map(v => `village/${slug(v.name)}`));
      if (target === 'machine') P().preload(sc.machines.map(m => `machine/${m.id}`));
    }
    if (withWelcome) items = [{ clip: 'prompt/welcome', gap_ms: 380 }, ...items];
    if (!(await say(items, line, id))) return;
    await maybeListen(id);
  };

  const maybeListen = async (id: number) => {
    if (!handsFreeRef.current || !micUsable()) {
      setPhase(flow.current.pending || flow.current.stage === 'consent' ? 'confirm' : 'idle');
      return;
    }
    await listenNow(id);
  };

  const listenNow = async (id: number) => {
    P().beep('listen');
    setListenError(null);
    setPhase('listening');
    const out = await speechRef.current.listen(SPEECH_LANG[langRef.current]);
    if (!alive(id)) return;
    if (!out.ok) {
      if (out.error === 'ABORTED') return;
      setListenError(out.error);
      const waiting = flow.current.pending || flow.current.stage === 'consent' ? 'confirm' : 'idle';
      if (out.error === 'NO_SPEECH') {
        flow.current.tries++;
        if (flow.current.tries < MAX_AUTO_TRIES) {
          if (!(await say([{ clip: 'prompt/no_speech' }], null, id))) return;
          await listenNow(id);
          return;
        }
      } else if (out.error === 'MIC_DENIED') {
        await say([{ clip: 'prompt/mic_off' }], null, id);
      }
      if (alive(id)) setPhase(waiting);
      return;
    }
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
      const q = promptLine('prompt/confirm_q');
      const line = { pa: `${res.display_pa} — ${q?.pa ?? ''}`, en: `${res.display_en} — ${q?.en ?? ''}` };
      if (!(await say(res.readback, line, id))) return;
      flow.current.tries = 0;
      await maybeListen(id);
      return;
    }
    flow.current.tries++;
    setProblem(res);
    if (res.partial) flow.current.partialPhone = res.partial;
    if (res.error_code === 'DATE_WHICH_KAL') flow.current.pendingKal = true;
    P().beep('error');
    const line = promptLine(res.prompt);
    if (!(await say(res.prompt ? [{ clip: res.prompt }] : [], line, id))) return;
    if (flow.current.tries < MAX_AUTO_TRIES || res.partial) await maybeListen(id);
    else setPhase('idle');
  };

  const onConfirm = async (res: VoiceResult, id: number) => {
    const st = flow.current.stage;
    if (!res.ok) {
      flow.current.tries++;
      if (!(await say([{ clip: 'prompt/confirm_unknown' }], promptLine('prompt/confirm_unknown'), id))) return;
      if (flow.current.tries < MAX_AUTO_TRIES) await maybeListen(id);
      else setPhase('confirm');
      return;
    }
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
      [st]: { value: p.value as string | number, display_pa: p.display_pa, display_en: p.display_en, readback: p.readback },
    };
    setAnswers(next);
    setPending(null);
    P().beep('ok');
    await ask(nextStage(next), id);
  };

  const outcomeSpeech = (req: RequestOut): { items: PlayItem[]; line: Line } => {
    const p = (k: string) => promptLine(`prompt/${k}`) ?? { pa: '', en: '' };
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
        line: { pa: `${pre.pa} ${sayDate(d, 'pa')} ${post.pa}`, en: `${pre.en} ${sayDate(d, 'en')}. ${post.en}` },
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
    const s = speechRef.current;
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
      setPhase(flow.current.pending || flow.current.stage === 'consent' ? 'confirm' : 'idle');
      return;
    }
    const id = cancel();
    flow.current.tries = 0;
    if (speech.permission === 'prompt' || speech.permission === 'unknown') {
      await speech.requestPermission();
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
      if (await say(p.readback, null, id)) await maybeListen(id);
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
        <div className="vb-card vb-center">ਲੋਡ ਹੋ ਰਿਹਾ ਹੈ… / Loading…</div>
      </div>
    );
  }

  const stepInfo = STEP_ORDER.includes(stage as VoiceStepId) ? script.steps.find(s => s.id === stage) : undefined;
  const micBlocked = speech.permission === 'denied';
  const showMic = stage !== 'intro' && stage !== 'done';
  const activeStep = stage as VoiceStepId;

  return (
    <div className="vb-page">
      <Link to="/desk" className="vb-type-link">
        ⌨️ ਕੀਬੋਰਡ ਨਾਲ ਫ਼ਾਰਮ ਭਰੋ / Type your booking instead →
      </Link>

      {/* Visible fallbacks */}
      {player.status === 'no-voices' && (
        <div className="vb-banner vb-banner-warning" role="status">
          🔇 <b>ਆਵਾਜ਼ਾਂ ਹਾਲੇ ਨਹੀਂ ਬਣੀਆਂ / Voice clips not made yet.</b> Questions are shown as text. Run{' '}
          <code>python tasks.py voices</code> once, then rebuild.
        </div>
      )}
      {player.status === 'ready' && player.missing.size > 0 && (
        <div className="vb-banner vb-banner-warning" role="status">
          🔈 {player.missing.size} clip(s) missing, shown as text. Run <code>python tasks.py voices</code>.
        </div>
      )}
      {!speech.secure && (
        <div className="vb-banner vb-banner-danger" role="alert">
          🔒 <b>{LISTEN_ERROR_TEXT.INSECURE.pa}</b> {LISTEN_ERROR_TEXT.INSECURE.en}
        </div>
      )}
      {speech.secure && !speech.supported && (
        <div className="vb-banner vb-banner-warning" role="status">
          {LISTEN_ERROR_TEXT.NOT_SUPPORTED.pa} <br /> {LISTEN_ERROR_TEXT.NOT_SUPPORTED.en}
        </div>
      )}
      {speech.secure && speech.supported && micBlocked && (
        <div className="vb-banner vb-banner-danger" role="alert">
          <div className="vb-banner-title">🔒 ਮਾਈਕ੍ਰੋਫ਼ੋਨ ਦੀ ਇਜਾਜ਼ਤ ਦਿਓ / Microphone permission required</div>
          <ol>
            <li>
              ਐਡਰੈੱਸ ਬਾਰ ਵਿੱਚ <b>{window.location.host}</b> ਦੇ ਖੱਬੇ ਪਾਸੇ 🔒 / ⚙️ ਆਈਕਨ ਦਬਾਓ। <span className="vb-en">Click the icon left of the address.</span>
            </li>
            <li>
              <b>Microphone → Allow</b> ਕਰੋ। <span className="vb-en">This page turns the mic on by itself once allowed. No reload needed.</span>
            </li>
          </ol>
          <button type="button" className="vb-btn vb-btn-danger" onClick={() => void speech.requestPermission()}>
            🔄 ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ / Try microphone again
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
                    {s.title_pa} <span className="vb-en">{s.title_en}</span>
                  </span>
                  {a && <span className="vb-step-value">{lang === 'en' ? a.display_en : a.display_pa}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      {stage === 'intro' && (
        <div className="vb-card vb-center vb-intro">
          <div className="vb-intro-mark" aria-hidden>🌾</div>
          <h1 className="vb-question">ਬੋਲ ਕੇ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਬੁੱਕ ਕਰੋ</h1>
          <p className="vb-sub">Book a machine turn by speaking, in Punjabi or English. Five short questions.</p>
          <div className="vb-row vb-wrap">
            <button type="button" className="vb-btn vb-btn-primary vb-btn-xl" onClick={() => void start('pa')}>
              ▶ ਪੰਜਾਬੀ ਵਿੱਚ ਸ਼ੁਰੂ ਕਰੋ
            </button>
            <button type="button" className="vb-btn vb-btn-outline vb-btn-xl" onClick={() => void start('en')}>
              ▶ Start in English
            </button>
          </div>
          {(players.pa.voiceName || players.en.voiceName) && (
            <p className="vb-credit">
              Voices: {[players.pa.voiceName, players.en.voiceName].filter(Boolean).join(' · ')}
            </p>
          )}
        </div>
      )}

      {(stepInfo || stage === 'consent') && (
        <div className={`vb-card vb-ask ${phase === 'listening' ? 'is-listening' : ''}`}>
          <div className="vb-status">
            <StatusPill phase={phase} />
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
              <input type="checkbox" checked={handsFree} onChange={toggleHandsFree} /> ਹੱਥ-ਮੁਕਤ / Hands-free
            </label>
          </div>

          {stage === 'consent' ? (
            <>
              <h2 className="vb-question">{pick(script.prompts['prompt/ask_consent'])}</h2>
              <p className="vb-sub">{pick(script.prompts['prompt/ask_consent'], true)}</p>
              <dl className="vb-summary">
                {script.steps.map(s => (
                  <div key={s.id}>
                    <dt>{s.title_pa} / {s.title_en}</dt>
                    <dd>{lang === 'en' ? answers[s.id]?.display_en : answers[s.id]?.display_pa}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <>
              <h2 className="vb-question">{pick({ pa: stepInfo!.ask_pa, en: stepInfo!.ask_en })}</h2>
              <p className="vb-sub">{pick({ pa: stepInfo!.ask_pa, en: stepInfo!.ask_en }, true)}</p>
            </>
          )}

          <button type="button" className="vb-btn vb-btn-outline" onClick={() => void replay()}>
            🔊 ਸਵਾਲ ਸੁਣੋ / Listen again
          </button>

          {subtitle && phase === 'speaking' && (
            <p className="vb-subtitle" aria-live="polite">
              {pick(subtitle)}
            </p>
          )}

          {/* Read-back waiting for yes/no */}
          {pending && stage !== 'consent' && (
            <div className="vb-confirm" aria-live="polite">
              <div className="vb-confirm-label">ਤੁਸੀਂ ਕਿਹਾ / You said</div>
              <div className="vb-confirm-value">{lang === 'en' ? pending.display_en : pending.display_pa}</div>
              {pending.display_en !== pending.display_pa && (
                <div className="vb-en">{lang === 'en' ? pending.display_pa : pending.display_en}</div>
              )}
              <div className="vb-confirm-q">ਕੀ ਇਹ ਠੀਕ ਹੈ ਜੀ? / Is this correct?</div>
              <div className="vb-row">
                <button type="button" className="vb-btn vb-btn-primary vb-btn-lg" onClick={() => void confirmButton(true)}>
                  ✓ ਹਾਂ ਜੀ / Yes
                </button>
                <button type="button" className="vb-btn vb-btn-light vb-btn-lg" onClick={() => void confirmButton(false)}>
                  ✗ ਨਹੀਂ / No
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
                {phase === 'submitting' ? 'ਸੇਵ ਹੋ ਰਿਹਾ ਹੈ… / Saving…' : '✓ ਬੁਕਿੰਗ ਪੱਕੀ ਕਰੋ / Confirm booking'}
              </button>
              <button type="button" className="vb-btn vb-btn-light vb-btn-lg" onClick={() => void confirmButton(false)}>
                ✗ ਹਾਲੇ ਨਹੀਂ / Not now
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
                  ਹੁਣ ਤੱਕ / So far: <b>{problem.partial}</b> ({problem.partial.length}/10)
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
                      {lang === 'en' ? alt.display_en : alt.display_pa}
                      {alt.display_en !== alt.display_pa && (
                        <span className="vb-en"> · {lang === 'en' ? alt.display_pa : alt.display_en}</span>
                      )}
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
                className={`vb-mic ${speech.listening ? 'is-on' : ''} ${speech.listening && speech.heardSomething ? 'is-hearing' : ''}`}
                onClick={() => void tapMic()}
                disabled={!speech.supported || !speech.secure || micBlocked || phase === 'submitting'}
                aria-label={speech.listening ? 'Stop listening' : 'Tap to speak'}
              >
                <span aria-hidden>🎙️</span>
              </button>
              <div className="vb-mic-label">
                {speech.listening ? 'ਸੁਣ ਰਿਹਾ ਹਾਂ… ਬੋਲੋ ਜੀ' : 'ਬੋਲਣ ਲਈ ਮਾਈਕ ਦਬਾਓ'}
                <span className="vb-en">
                  {speech.listening ? 'Listening… speak now' : `Tap the mic to speak in ${lang === 'en' ? 'English' : 'Punjabi'}`}
                </span>
              </div>
              {(speech.interim || heard) && (
                <div className="vb-heard">
                  ਸੁਣਿਆ / Heard: <q>{speech.interim || heard}</q>
                </div>
              )}
              {listenError && listenError !== 'ABORTED' && (
                <div className="vb-listen-error">
                  {LISTEN_ERROR_TEXT[listenError].pa} <span className="vb-en">{LISTEN_ERROR_TEXT[listenError].en}</span>
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
                      {m.name_pa}
                      <span className="vb-en">{m.name_en}</span>
                    </button>
                  ))}
                </div>
              )}
              {activeStep === 'date' && (
                <div className="vb-row vb-wrap">
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('ਅੱਜ', true)}>ਅੱਜ / Today</button>
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('ਬੀਤਿਆ ਕੱਲ੍ਹ', true)}>ਬੀਤਿਆ ਕੱਲ੍ਹ / Yesterday</button>
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ', true)}>ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ / Tomorrow</button>
                  <button type="button" className="vb-btn vb-btn-choice" onClick={() => void sendText('ਹਾਲੇ ਪਤਾ ਨਹੀਂ', true)}>ਹਾਲੇ ਪਤਾ ਨਹੀਂ / Not known yet</button>
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
                    ⌨️ ਜਾਂ ਇੱਥੇ ਲਿਖ ਕੇ ਜਵਾਬ ਦਿਓ / Or type your reply:
                  </label>
                  <div className="vb-row">
                    <input
                      id="vb-typed"
                      className="vb-input"
                      value={typed}
                      onChange={e => setTyped(e.target.value)}
                      placeholder={`${stepInfo.hint_pa} — ${stepInfo.hint_en}`}
                      inputMode={activeStep === 'phone' ? 'numeric' : activeStep === 'acres' ? 'decimal' : 'text'}
                      list={activeStep === 'village' ? 'vb-villages' : undefined}
                      autoComplete="off"
                    />
                    <button type="submit" className="vb-btn vb-btn-primary" disabled={!typed.trim()}>
                      ਭੇਜੋ / Send ↵
                    </button>
                  </div>
                  {activeStep === 'village' && (
                    <datalist id="vb-villages">
                      {script.villages.map(v => (
                        <option key={v.name} value={v.name}>
                          {v.name_pa}
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
          <div className="vb-row">
            <button type="button" className="vb-btn vb-btn-outline" onClick={() => void replay()}>
              🔊 ਦੁਬਾਰਾ ਸੁਣੋ / Hear again
            </button>
            <button type="button" className="vb-btn vb-btn-primary" onClick={restart}>
              ➕ ਨਵੀਂ ਬੁਕਿੰਗ / New booking
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusPill({ phase }: { phase: Phase }) {
  const map: Record<Phase, string> = {
    idle: 'ਤੁਹਾਡੀ ਵਾਰੀ / Your turn',
    speaking: '🔊 ਬੋਲ ਰਿਹਾ ਹਾਂ / Speaking',
    listening: '🎙️ ਸੁਣ ਰਿਹਾ ਹਾਂ / Listening',
    thinking: '… ਸਮਝ ਰਿਹਾ ਹਾਂ / Understanding',
    confirm: 'ਹਾਂ ਜਾਂ ਨਹੀਂ? / Yes or no?',
    submitting: 'ਸੇਵ ਹੋ ਰਿਹਾ ਹੈ / Saving',
  };
  return <span className={`vb-pill vb-pill-${phase}`}>{map[phase]}</span>;
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
