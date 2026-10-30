/**
 * VoicePlayer — plays Punjabi voice clips back to back with no dead air.
 *
 * Every clip is decoded once with Web Audio, its leading and trailing silence
 * is measured and cut at play time (sample-accurate), and its loudness is
 * evened out, so a read-back stitched from several clips ("ਤੁਹਾਡਾ ਨੰਬਰ ਹੈ" +
 * ten digits + "ਕੀ ਇਹ ਠੀਕ ਹੈ ਜੀ?") sounds like one voice speaking.
 *
 * Clips live at /audio/<pa|en>/<id>.mp3 and are listed in that folder's
 * manifest.json (made by `python tasks.py voices`). One player per language. A clip that is missing is skipped and
 * reported through `missing`, so the page can show it and keep working.
 */
import { getAudioClip, getVoiceManifest } from '../api';
import type { PlayItem, VoiceLang, VoiceManifest } from './types';

export interface SpeechBounds {
  start: number; // first sample to play
  end: number; // one past the last sample to play
  voicedRms: number;
}

/**
 * Find where speech starts and ends in a clip. Exported for tests.
 * 10 ms windows; a window counts as speech when it is within 30 dB of the
 * loudest window. A little padding is kept so soft first and last sounds
 * (ਸ, ਹ, a falling "ਜੀ") are not clipped.
 */
export function findSpeechBounds(data: Float32Array, sampleRate: number): SpeechBounds {
  const win = Math.max(1, Math.round(sampleRate * 0.01));
  const n = Math.floor(data.length / win);
  if (n === 0) return { start: 0, end: data.length, voicedRms: 0 };
  const rms = new Float32Array(n);
  let max = 0;
  for (let w = 0; w < n; w++) {
    let sum = 0;
    const base = w * win;
    for (let i = 0; i < win; i++) {
      const v = data[base + i];
      sum += v * v;
    }
    rms[w] = Math.sqrt(sum / win);
    if (rms[w] > max) max = rms[w];
  }
  if (max < 1e-4) return { start: 0, end: data.length, voicedRms: 0 };
  const thr = Math.max(max * 0.0316, 0.0015); // -30 dB below the peak window
  let first = 0;
  while (first < n && rms[first] < thr) first++;
  let last = n - 1;
  while (last > first && rms[last] < thr) last--;
  let voicedSum = 0;
  let voicedCount = 0;
  for (let w = first; w <= last; w++) {
    if (rms[w] >= thr) {
      voicedSum += rms[w] * rms[w];
      voicedCount++;
    }
  }
  const leadPad = Math.round(sampleRate * 0.025);
  const tailPad = Math.round(sampleRate * 0.06);
  return {
    start: Math.max(0, first * win - leadPad),
    end: Math.min(data.length, (last + 1) * win + tailPad),
    voicedRms: voicedCount ? Math.sqrt(voicedSum / voicedCount) : 0,
  };
}

let shared: AudioContext | null = null;

/** One AudioContext for the whole page (browsers limit how many may exist). */
function sharedContext(): AudioContext | null {
  if (shared) return shared;
  const Ctor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  shared = new Ctor({ latencyHint: 'interactive' });
  return shared;
}

interface Prepared {
  buffer: AudioBuffer;
  offset: number; // seconds into the buffer
  duration: number; // seconds to play
  gain: number;
}

type Status = 'loading' | 'ready' | 'no-voices';

const TARGET_RMS = 0.11;

export class VoicePlayer {
  readonly lang: VoiceLang;
  status: Status = 'loading';
  voiceName = '';
  readonly missing = new Set<string>();

  private ctx: AudioContext | null = null;
  private manifest: VoiceManifest | null = null;
  private cache = new Map<string, Promise<Prepared | null>>();
  private active: AudioScheduledSourceNode[] = [];
  private token = 0;
  private finish: ((done: boolean) => void) | null = null;
  private listeners = new Set<() => void>();

  private readonly base: string;
  private initPromise: Promise<void> | null = null;

  constructor(lang: VoiceLang) {
    this.lang = lang;
    this.base = `/audio/${lang}/`;
  }

  /** Load the manifest once; later calls return the same promise. */
  init(): Promise<void> {
    this.initPromise ??= this.loadManifest();
    return this.initPromise;
  }

  private async loadManifest(): Promise<void> {
    this.manifest = await getVoiceManifest(this.lang);
    const count = this.manifest ? Object.keys(this.manifest.clips).length : 0;
    this.status = count > 0 ? 'ready' : 'no-voices';
    this.voiceName = this.manifest?.voice ?? '';
    this.emit();
  }

  /** Re-render hook for React. */
  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(): void {
    this.listeners.forEach(fn => fn());
  }

  has(id: string): boolean {
    return !!this.manifest?.clips[id];
  }

  /** Must run inside a click/tap the first time: browsers block sound until then. */
  unlock(): void {
    if (!this.ctx) {
      this.ctx = sharedContext();
      if (!this.ctx) return;
    }
    if (this.ctx.state === 'suspended') void this.ctx.resume();
  }

  get unlocked(): boolean {
    return !!this.ctx && this.ctx.state === 'running';
  }

  preload(ids: string[]): void {
    for (const id of ids) void this.load(id);
  }

  private load(id: string): Promise<Prepared | null> {
    const hit = this.cache.get(id);
    if (hit) return hit;
    const p = this.fetchAndPrepare(id);
    this.cache.set(id, p);
    return p;
  }

  private async fetchAndPrepare(id: string): Promise<Prepared | null> {
    const entry = this.manifest?.clips[id];
    if (!entry) {
      this.markMissing(id);
      return null;
    }
    try {
      if (!this.ctx) this.unlock();
      if (!this.ctx) return null;
      const bytes = await getAudioClip(this.base + entry.file);
      const buffer = await this.ctx.decodeAudioData(bytes);
      const b = findSpeechBounds(buffer.getChannelData(0), buffer.sampleRate);
      const gain = b.voicedRms > 0 ? Math.min(3, Math.max(0.5, TARGET_RMS / b.voicedRms)) : 1;
      return {
        buffer,
        offset: b.start / buffer.sampleRate,
        duration: Math.max(0.02, (b.end - b.start) / buffer.sampleRate),
        gain,
      };
    } catch {
      this.cache.delete(id); // allow a retry later (e.g. the network came back)
      this.markMissing(id);
      return null;
    }
  }

  private markMissing(id: string): void {
    if (!this.missing.has(id)) {
      this.missing.add(id);
      this.emit();
    }
  }

  /**
   * Play clips back to back. Resolves false only when interrupted (stop() or a
   * newer play()). With no clips, or sound blocked, it resolves true at once so
   * the conversation carries on with the on-screen text.
   */
  async play(items: PlayItem[]): Promise<boolean> {
    this.stop();
    const my = ++this.token;
    if (this.status !== 'ready' || items.length === 0) return true;
    this.unlock();
    const ctx = this.ctx;
    if (!ctx) return true;
    const prepared = await Promise.all(items.map(it => this.load(it.clip)));
    if (my !== this.token) return false;
    if (ctx.state === 'suspended') {
      try {
        await ctx.resume();
      } catch {
        return true;
      }
    }
    if (ctx.state !== 'running' || my !== this.token) return my === this.token;

    let t = ctx.currentTime + 0.04;
    let last: AudioScheduledSourceNode | null = null;
    prepared.forEach((p, i) => {
      if (!p) return;
      const src = ctx.createBufferSource();
      src.buffer = p.buffer;
      const g = ctx.createGain();
      const fade = Math.min(0.008, p.duration / 4);
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(p.gain, t + fade);
      g.gain.setValueAtTime(p.gain, t + p.duration - fade);
      g.gain.linearRampToValueAtTime(0, t + p.duration);
      src.connect(g).connect(ctx.destination);
      src.start(t, p.offset, p.duration);
      this.active.push(src);
      last = src;
      t += p.duration + Math.max(0, items[i].gap_ms ?? 40) / 1000;
    });
    if (!last) return true;
    const lastSrc: AudioScheduledSourceNode = last;
    return new Promise<boolean>(resolve => {
      this.finish = resolve;
      lastSrc.onended = () => {
        if (my !== this.token) return;
        this.active = [];
        this.finish = null;
        resolve(true);
      };
    });
  }

  stop(): void {
    this.token++;
    for (const s of this.active) {
      try {
        s.onended = null;
        s.stop();
      } catch {
        /* already stopped */
      }
    }
    this.active = [];
    if (this.finish) {
      const f = this.finish;
      this.finish = null;
      f(false);
    }
  }

  /** Short tones: a rising "go ahead" before listening, a soft "got it", a low "try again". */
  beep(kind: 'listen' | 'ok' | 'error'): void {
    this.unlock();
    const ctx = this.ctx;
    if (!ctx || ctx.state !== 'running') return;
    const notes = kind === 'listen' ? [660, 880] : kind === 'ok' ? [880, 1175] : [330, 262];
    let t = ctx.currentTime + 0.01;
    for (const f of notes) {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = 'sine';
      o.frequency.value = f;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.12, t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.11);
      o.connect(g).connect(ctx.destination);
      o.start(t);
      o.stop(t + 0.12);
      t += 0.09;
    }
  }
}
