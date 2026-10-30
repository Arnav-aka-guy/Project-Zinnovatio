/**
 * useSpeechInput — Punjabi speech-to-text with the browser's Web Speech API.
 *
 * - Watches the microphone permission live, so when someone switches it to
 *   "Allow" in the address bar the page recovers without a reload.
 * - Detects the two silent killers: a page opened over plain http on a LAN IP
 *   (browsers block the mic there) and browsers with no speech support.
 * - Returns up to 5 guesses per answer; the server tries each in order.
 * - Language is a BCP-47 tag: 'pa-IN' (Punjabi, Gurmukhi text) or 'en-IN' (Indian English).
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export type MicPermission = 'granted' | 'denied' | 'prompt' | 'unknown';

export type ListenError =
  | 'NOT_SUPPORTED'
  | 'INSECURE'
  | 'MIC_DENIED'
  | 'NO_MIC'
  | 'NO_SPEECH'
  | 'NETWORK'
  | 'ABORTED'
  | 'UNKNOWN';

export type ListenOutcome = { ok: true; texts: string[] } | { ok: false; error: ListenError };

// Minimal typings: the Web Speech API is not in every TypeScript DOM lib.
interface SRAlternative {
  transcript: string;
  confidence: number;
}
interface SRResult {
  readonly length: number;
  readonly isFinal: boolean;
  [i: number]: SRAlternative;
}
interface SREvent {
  readonly resultIndex: number;
  readonly results: { readonly length: number; [i: number]: SRResult };
}
interface SRErrorEvent {
  readonly error: string;
}
interface SR {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: SRErrorEvent) => void) | null;
  onend: (() => void) | null;
  onspeechstart: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SRCtor = new () => SR;

function getRecognizer(): SRCtor | null {
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const MAX_LISTEN_MS = 12000;

export function useSpeechInput(lang = 'pa-IN') {
  const supported = typeof window !== 'undefined' && getRecognizer() !== null;
  const secure = typeof window !== 'undefined' && window.isSecureContext;
  const [permission, setPermission] = useState<MicPermission>('unknown');
  const [listening, setListening] = useState(false);
  const [heardSomething, setHeardSomething] = useState(false);
  const [interim, setInterim] = useState('');
  const current = useRef<SR | null>(null);

  // Live permission state. Chrome fires `change` when the user flips the site setting.
  useEffect(() => {
    let status: PermissionStatus | null = null;
    let cancelled = false;
    const perms = navigator.permissions;
    if (!perms?.query) return;
    perms
      .query({ name: 'microphone' as PermissionName })
      .then(s => {
        if (cancelled) return;
        status = s;
        setPermission(s.state as MicPermission);
        s.onchange = () => setPermission(s.state as MicPermission);
      })
      .catch(() => setPermission('unknown'));
    return () => {
      cancelled = true;
      if (status) status.onchange = null;
    };
  }, []);

  /** Ask for the mic once (shows the browser prompt when allowed to). */
  const requestPermission = useCallback(async (): Promise<MicPermission> => {
    if (!navigator.mediaDevices?.getUserMedia) return 'unknown';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(t => t.stop());
      setPermission('granted');
      return 'granted';
    } catch (err) {
      const name = (err as DOMException)?.name;
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        setPermission('denied');
        return 'denied';
      }
      return 'unknown';
    }
  }, []);

  const abort = useCallback(() => {
    const r = current.current;
    current.current = null;
    if (r) {
      try {
        r.abort();
      } catch {
        /* not running */
      }
    }
    setListening(false);
    setInterim('');
  }, []);

  /** Listen for one answer. `langOverride` wins over the hook's language (used right after a switch). */
  const listen = useCallback((langOverride?: string): Promise<ListenOutcome> => {
    abort();
    const Ctor = getRecognizer();
    if (!Ctor) return Promise.resolve({ ok: false, error: 'NOT_SUPPORTED' });
    if (!window.isSecureContext) return Promise.resolve({ ok: false, error: 'INSECURE' });

    return new Promise<ListenOutcome>(resolve => {
      const r = new Ctor();
      current.current = r;
      r.lang = langOverride ?? lang;
      r.continuous = false;
      r.interimResults = true;
      r.maxAlternatives = 5;

      let finals: string[] = [];
      let lastInterim = '';
      let error: ListenError | null = null;
      let settled = false;
      const timer = window.setTimeout(() => {
        try {
          r.stop();
        } catch {
          /* ignore */
        }
      }, MAX_LISTEN_MS);

      const settle = (out: ListenOutcome) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        if (current.current === r) current.current = null;
        setListening(false);
        setInterim('');
        resolve(out);
      };

      r.onspeechstart = () => setHeardSomething(true);
      r.onresult = e => {
        let text = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i];
          if (res.isFinal) {
            const alts: string[] = [];
            for (let a = 0; a < res.length; a++) {
              const t = res[a]?.transcript?.trim();
              if (t) alts.push(t);
            }
            finals = alts.length ? alts : finals;
          } else {
            text += res[0]?.transcript ?? '';
          }
        }
        lastInterim = text.trim() || lastInterim;
        setInterim(text.trim());
      };
      r.onerror = e => {
        error =
          e.error === 'not-allowed' || e.error === 'service-not-allowed'
            ? 'MIC_DENIED'
            : e.error === 'no-speech'
              ? 'NO_SPEECH'
              : e.error === 'audio-capture'
                ? 'NO_MIC'
                : e.error === 'network'
                  ? 'NETWORK'
                  : e.error === 'aborted'
                    ? 'ABORTED'
                    : 'UNKNOWN';
        if (error === 'MIC_DENIED') setPermission('denied');
      };
      r.onend = () => {
        if (finals.length) return settle({ ok: true, texts: finals });
        if (!error && lastInterim) return settle({ ok: true, texts: [lastInterim] });
        settle({ ok: false, error: error ?? 'NO_SPEECH' });
      };

      try {
        setHeardSomething(false);
        setListening(true);
        r.start();
      } catch {
        settle({ ok: false, error: 'UNKNOWN' });
      }
    });
  }, [abort, lang]);

  useEffect(() => abort, [abort]);

  return { supported, secure, permission, listening, heardSomething, interim, listen, abort, requestPermission };
}
