/**
 * useCloudSpeech — records one spoken answer and sends it to Google Speech-to-Text
 * through the server (POST /api/voice/transcribe).
 *
 * - Works on every browser with a microphone, iPhone included (the browser's own
 *   speech recognition does not exist on Safari or Firefox).
 * - Google hears Punjabi, Hindi and English at once, so the farmer can answer in
 *   any of them, whatever language the questions are in.
 * - Knows by itself when the farmer has finished: it measures the room's noise
 *   for a moment, waits for speech, and stops after a short silence. Pauses inside
 *   an answer (a phone number said in two halves) are allowed for.
 * - Audio is sent as 16 kHz mono 16-bit WAV, the format Google reads best.
 *
 * Same shape as useSpeechInput (speech.ts), so the page can use either.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, transcribeVoice } from '../api';
import type { ListenError, ListenOutcome, MicPermission } from './speech';
import type { VoiceLang, VoiceParseStep } from './types';

const TARGET_RATE = 16000;
const FRAME = 4096;
const CALIBRATE_MS = 300;
const NO_SPEECH_MS = 7000;
const MAX_MS = 15000;
const PRE_ROLL_MS = 400;

export interface ListenOptions {
  /** Silence that ends the answer. Longer for phone numbers (people pause between halves). */
  endSilenceMs?: number;
  step?: VoiceParseStep;
}

export type CloudOutcome = ListenOutcome & { language?: string | null; reason?: string };

/** Downsample float audio to 16 kHz by averaging, then write a PCM WAV file. Exported for tests. */
export function encodeWav(chunks: Float32Array[], inputRate: number): Blob {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const ratio = inputRate / TARGET_RATE;
  const outLen = Math.floor(total / ratio);
  const pcm = new Int16Array(outLen);
  let ci = 0;
  let offset = 0; // index inside chunks[ci]
  let pos = 0; // absolute input position consumed
  for (let o = 0; o < outLen; o++) {
    const end = Math.floor((o + 1) * ratio);
    let sum = 0;
    let count = 0;
    while (pos < end && ci < chunks.length) {
      sum += chunks[ci][offset];
      count++;
      pos++;
      offset++;
      if (offset >= chunks[ci].length) {
        ci++;
        offset = 0;
      }
    }
    const v = count ? sum / count : 0;
    pcm[o] = Math.max(-32768, Math.min(32767, Math.round(v * 32767)));
  }
  const header = new ArrayBuffer(44);
  const dv = new DataView(header);
  const str = (at: number, s: string) => [...s].forEach((ch, i) => dv.setUint8(at + i, ch.charCodeAt(0)));
  str(0, 'RIFF');
  dv.setUint32(4, 36 + pcm.byteLength, true);
  str(8, 'WAVE');
  str(12, 'fmt ');
  dv.setUint32(16, 16, true);
  dv.setUint16(20, 1, true); // PCM
  dv.setUint16(22, 1, true); // mono
  dv.setUint32(24, TARGET_RATE, true);
  dv.setUint32(28, TARGET_RATE * 2, true);
  dv.setUint16(32, 2, true);
  dv.setUint16(34, 16, true);
  str(36, 'data');
  dv.setUint32(40, pcm.byteLength, true);
  return new Blob([header, pcm.buffer], { type: 'audio/wav' });
}

function rms(data: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
  return Math.sqrt(sum / data.length);
}

type Ctx = AudioContext;

export function useCloudSpeech() {
  const supported =
    typeof window !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    !!(window.AudioContext ?? (window as unknown as { webkitAudioContext?: unknown }).webkitAudioContext);
  const secure = typeof window !== 'undefined' && window.isSecureContext;
  const [permission, setPermission] = useState<MicPermission>('unknown');
  const [listening, setListening] = useState(false);
  const [heardSomething, setHeardSomething] = useState(false);
  const [level, setLevel] = useState(0);
  const [sending, setSending] = useState(false);
  const stream = useRef<MediaStream | null>(null);
  const ctx = useRef<Ctx | null>(null);
  const stopCurrent = useRef<((aborted: boolean) => void) | null>(null);

  useEffect(() => {
    let status: PermissionStatus | null = null;
    let cancelled = false;
    navigator.permissions
      ?.query({ name: 'microphone' as PermissionName })
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

  const openMic = useCallback(async (): Promise<MediaStream> => {
    const live = stream.current?.getAudioTracks().some(t => t.readyState === 'live');
    if (stream.current && live) return stream.current;
    const s = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    stream.current = s;
    setPermission('granted');
    return s;
  }, []);

  const requestPermission = useCallback(async (): Promise<MicPermission> => {
    try {
      await openMic();
      return 'granted';
    } catch (err) {
      const name = (err as DOMException)?.name;
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        setPermission('denied');
        return 'denied';
      }
      return 'unknown';
    }
  }, [openMic]);

  const abort = useCallback(() => {
    stopCurrent.current?.(true);
    stopCurrent.current = null;
    setListening(false);
    setLevel(0);
  }, []);

  /** Record one answer, then turn it into text. */
  const listen = useCallback(
    async (lang: VoiceLang, opts: ListenOptions = {}): Promise<CloudOutcome> => {
      abort();
      if (!supported) return { ok: false, error: 'NOT_SUPPORTED' };
      if (!window.isSecureContext) return { ok: false, error: 'INSECURE' };
      let mic: MediaStream;
      try {
        mic = await openMic();
      } catch (err) {
        const name = (err as DOMException)?.name;
        if (name === 'NotAllowedError' || name === 'SecurityError') {
          setPermission('denied');
          return { ok: false, error: 'MIC_DENIED' };
        }
        return { ok: false, error: name === 'NotFoundError' ? 'NO_MIC' : 'UNKNOWN' };
      }
      const Ctor =
        window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      ctx.current ??= new Ctor();
      const ac = ctx.current;
      if (ac.state === 'suspended') await ac.resume().catch(() => undefined);

      const endSilence = opts.endSilenceMs ?? 1300;
      const recorded = await new Promise<{ chunks: Float32Array[]; aborted: boolean; heard: boolean }>(resolve => {
        const source = ac.createMediaStreamSource(mic);
        const proc = ac.createScriptProcessor(FRAME, 1, 1);
        const frameMs = (FRAME / ac.sampleRate) * 1000;
        const preRoll: Float32Array[] = [];
        const chunks: Float32Array[] = [];
        let elapsed = 0;
        let noise = 0;
        let noiseFrames = 0;
        let threshold = 0.02;
        let loudRun = 0;
        let started = false;
        let silentMs = 0;
        let smooth = 0;
        let lastLevelAt = 0;
        let done = false;

        // Safety net: even if the audio stops arriving, the turn ends.
        const watchdog = window.setTimeout(() => finish(false), MAX_MS + 1500);
        const finish = (aborted: boolean) => {
          if (done) return;
          done = true;
          window.clearTimeout(watchdog);
          proc.onaudioprocess = null;
          try {
            source.disconnect();
            proc.disconnect();
          } catch {
            /* already disconnected */
          }
          if (stopCurrent.current === finish) stopCurrent.current = null;
          resolve({ chunks, aborted, heard: started });
        };
        stopCurrent.current = finish;

        proc.onaudioprocess = e => {
          const frame = new Float32Array(e.inputBuffer.getChannelData(0));
          const r = rms(frame);
          elapsed += frameMs;
          smooth = smooth * 0.6 + r * 0.4;
          if (elapsed - lastLevelAt > 90) {
            lastLevelAt = elapsed;
            setLevel(Math.min(1, smooth / Math.max(threshold * 4, 0.05)));
          }
          if (elapsed <= CALIBRATE_MS) {
            noise += r;
            noiseFrames++;
            threshold = Math.min(0.08, Math.max(0.012, (noise / noiseFrames) * 2.5));
          }
          if (!started) {
            preRoll.push(frame);
            while (preRoll.length * frameMs > PRE_ROLL_MS) preRoll.shift();
            loudRun = r > threshold ? loudRun + 1 : 0;
            if (loudRun >= 2 && elapsed > CALIBRATE_MS) {
              started = true;
              setHeardSomething(true);
              chunks.push(...preRoll);
            } else if (elapsed > NO_SPEECH_MS) {
              finish(false);
            }
            return;
          }
          chunks.push(frame);
          silentMs = r < threshold * 0.8 ? silentMs + frameMs : 0;
          if (silentMs >= endSilence || elapsed >= MAX_MS) finish(false);
        };
        source.connect(proc);
        proc.connect(ac.destination); // needed for onaudioprocess to run; the output is silent
        setHeardSomething(false);
        setListening(true);
      });
      setListening(false);
      setLevel(0);
      if (recorded.aborted) return { ok: false, error: 'ABORTED' };
      if (!recorded.heard) return { ok: false, error: 'NO_SPEECH' };

      setSending(true);
      try {
        const wav = encodeWav(recorded.chunks, ac.sampleRate);
        const res = await transcribeVoice(wav, lang, opts.step);
        if (!res.texts.length) return { ok: false, error: 'NO_SPEECH' };
        return { ok: true, texts: res.texts, language: res.language };
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.error_code === 'NETWORK_DOWN') return { ok: false, error: 'NETWORK' };
          if (err.status === 401) return { ok: false, error: 'UNKNOWN', reason: 'signed_out' };
          const reason = String((err.details as { reason?: string })?.reason ?? err.error_code);
          return { ok: false, error: 'CLOUD_DOWN', reason };
        }
        return { ok: false, error: 'UNKNOWN' };
      } finally {
        setSending(false);
      }
    },
    [abort, openMic, supported],
  );

  useEffect(
    () => () => {
      stopCurrent.current?.(true);
      stream.current?.getTracks().forEach(t => t.stop());
      void ctx.current?.close().catch(() => undefined);
    },
    [],
  );

  return {
    supported,
    secure,
    permission,
    listening,
    heardSomething,
    level,
    sending,
    interim: '',
    listen,
    abort,
    requestPermission,
  };
}

export type { ListenError };
