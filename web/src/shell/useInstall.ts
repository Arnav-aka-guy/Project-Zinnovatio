/** "Install app" support: Android/desktop Chrome prompt, iOS instructions, and standalone detection. */
import { useEffect, useState } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

let deferred: BeforeInstallPromptEvent | null = null;
const listeners = new Set<() => void>();
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    deferred = e as BeforeInstallPromptEvent;
    listeners.forEach(fn => fn());
  });
  window.addEventListener('appinstalled', () => {
    deferred = null;
    listeners.forEach(fn => fn());
  });
}

export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  const nav = navigator as Navigator & { standalone?: boolean };
  return window.matchMedia?.('(display-mode: standalone)').matches || nav.standalone === true;
}

export function isIOS(): boolean {
  const ua = navigator.userAgent;
  return /iPhone|iPad|iPod/.test(ua) || (ua.includes('Mac') && 'ontouchend' in document);
}

export function useInstall() {
  const [, bump] = useState(0);
  useEffect(() => {
    const fn = () => bump(n => n + 1);
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  }, []);
  const standalone = isStandalone();
  return {
    standalone,
    canPrompt: !!deferred && !standalone,
    iosHint: !standalone && !deferred && isIOS(),
    async prompt(): Promise<boolean> {
      if (!deferred) return false;
      const e = deferred;
      await e.prompt();
      const choice = await e.userChoice.catch(() => ({ outcome: 'dismissed' as const }));
      deferred = null;
      listeners.forEach(fn => fn());
      return choice.outcome === 'accepted';
    },
  };
}

/** Online/offline state for the "No signal" bar. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine));
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online', up);
      window.removeEventListener('offline', down);
    };
  }, []);
  return online;
}

/** True when the screen is phone-sized. Matches the CSS breakpoint in mobile.css. */
export function useIsPhone(query = '(max-width: 900px)'): boolean {
  const [match, setMatch] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const fn = () => setMatch(mq.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, [query]);
  return match;
}
