/**
 * Web push on this device: turn alerts on or off, and keep the server's copy fresh.
 *
 * Staff pages use the service worker at scope "/"; driver links use a second
 * registration at scope "/driver/" and farmer pages a third at "/farmer/".
 * A browser gives each registration its own push address, so one phone can be
 * a desk, a driver and a farmer phone in a demo without one switching another off.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  addDriverPush,
  addFarmerPush,
  addPushSubscription,
  getHealth,
  removeDriverPush,
  removeFarmerPush,
  removePushSubscription,
  sendDriverTestAlert,
  sendFarmerTestAlert,
  sendTestAlert,
} from '../api';
import type { PushSubscriptionBody, PushTestResult } from '../types';
import { isIOS, isStandalone } from './useInstall';

export type PushTarget = { kind: 'staff' } | { kind: 'driver'; token: string } | { kind: 'farmer'; token: string };

/** What this device can do. */
export type PushState =
  | 'checking'
  | 'on'
  | 'off'
  | 'blocked' // the person said no in the browser; only browser settings can undo it
  | 'ios-install' // iPhone: alerts work once Vaari is on the home screen
  | 'insecure' // needs https (or localhost)
  | 'unsupported';

const scopeFor = (t: PushTarget) => (t.kind === 'staff' ? '/' : `/${t.kind}/`);

export function pushSupported(): boolean {
  return typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

function base64UrlToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function registration(target: PushTarget, create: boolean): Promise<ServiceWorkerRegistration | null> {
  const scope = scopeFor(target);
  const probe = target.kind === 'staff' ? '/' : `/${target.kind}/${target.token}`;
  const found = await navigator.serviceWorker.getRegistration(probe);
  if (found && new URL(found.scope).pathname === scope) return found;
  if (!create) return null;
  const reg = await navigator.serviceWorker.register('/sw.js', { scope });
  if (!reg.active) {
    await new Promise<void>(resolve => {
      const sw = reg.installing || reg.waiting;
      if (!sw) return resolve();
      sw.addEventListener('statechange', () => sw.state === 'activated' && resolve());
      setTimeout(resolve, 4000);
    });
  }
  return reg;
}

function toBody(sub: PushSubscription, label?: string): PushSubscriptionBody {
  const json = sub.toJSON() as { endpoint: string; keys?: { p256dh?: string; auth?: string } };
  return {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? '', auth: json.keys?.auth ?? '' },
    label: label ?? deviceLabel(),
  };
}

function deviceLabel(): string {
  const ua = navigator.userAgent;
  const os = /Android/.test(ua) ? 'Android' : isIOS() ? 'iPhone' : /Windows/.test(ua) ? 'Windows' : /Mac/.test(ua) ? 'Mac' : 'Computer';
  const br = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Browser';
  return `${br} on ${os}`;
}

async function save(target: PushTarget, sub: PushSubscription): Promise<void> {
  const body = toBody(sub);
  if (target.kind === 'driver') await addDriverPush(target.token, body);
  else if (target.kind === 'farmer') await addFarmerPush(target.token, body);
  else await addPushSubscription(body);
}

async function stateNow(target: PushTarget): Promise<PushState> {
  if (!window.isSecureContext) return 'insecure';
  if (!pushSupported()) return isIOS() && !isStandalone() ? 'ios-install' : 'unsupported';
  if (Notification.permission === 'denied') return 'blocked';
  const reg = await registration(target, false);
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  return sub && Notification.permission === 'granted' ? 'on' : 'off';
}

/** Turn alerts on: ask permission, subscribe, tell the server. Throws a plain-English Error on failure. */
export async function enablePush(target: PushTarget): Promise<void> {
  const health = await getHealth();
  const key = health.notifications?.vapid_public_key;
  if (!key) throw new Error('The server has no push key. Ask the admin to check the alert settings.');
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Alerts were not allowed on this device.');
  const reg = await registration(target, true);
  if (!reg) throw new Error('This browser could not start alerts.');
  let sub = await reg.pushManager.getSubscription();
  const wanted = base64UrlToBytes(key);
  if (sub) {
    const current = sub.options.applicationServerKey;
    const same = current && new Uint8Array(current).every((b, i) => b === wanted[i]);
    if (!same) {
      await sub.unsubscribe();
      sub = null;
    }
  }
  if (!sub) {
    try {
      sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: wanted });
    } catch {
      throw new Error('The browser’s push service did not answer. Check the internet and try again.');
    }
  }
  await save(target, sub);
}

export async function disablePush(target: PushTarget): Promise<void> {
  const reg = await registration(target, false);
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  if (!sub) return;
  const endpoint = sub.endpoint;
  await sub.unsubscribe().catch(() => undefined);
  if (target.kind === 'driver') await removeDriverPush(target.token, endpoint).catch(() => undefined);
  else if (target.kind === 'farmer') await removeFarmerPush(target.token, endpoint).catch(() => undefined);
  else await removePushSubscription(endpoint).catch(() => undefined);
}

export async function testPush(target: PushTarget): Promise<PushTestResult> {
  const reg = await registration(target, false);
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  if (target.kind === 'driver') return sendDriverTestAlert(target.token, sub?.endpoint);
  if (target.kind === 'farmer') return sendFarmerTestAlert(target.token, sub?.endpoint);
  return sendTestAlert(sub?.endpoint);
}

/** Re-send an existing subscription (after sign-in, a role change, or a server restore). Quiet on errors. */
export async function resyncPush(target: PushTarget): Promise<void> {
  if (!pushSupported() || !window.isSecureContext || Notification.permission !== 'granted') return;
  const reg = await registration(target, false);
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  if (sub) await save(target, sub).catch(() => undefined);
}

export function usePush(target: PushTarget | null) {
  const [state, setState] = useState<PushState>('checking');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = target ? (target.kind === 'staff' ? 'staff' : `${target.kind}:${target.token}`) : '';

  const refresh = useCallback(async () => {
    if (!target) return;
    try {
      setState(await stateNow(target));
    } catch {
      setState('unsupported');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = useCallback(
    async (fn: () => Promise<unknown>) => {
      setBusy(true);
      setError(null);
      try {
        await fn();
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Something went wrong.');
      } finally {
        setBusy(false);
        await refresh();
      }
    },
    [refresh],
  );

  return {
    state,
    busy,
    error,
    enable: () => target && run(() => enablePush(target)),
    disable: () => target && run(() => disablePush(target)),
    test: async (): Promise<PushTestResult | null> => {
      if (!target) return null;
      setError(null);
      try {
        return await testPush(target);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Test failed.');
        return null;
      }
    },
  };
}

/** Text for each state, used by the bell panel and the driver page. */
export const PUSH_HINT: Record<PushState, string> = {
  checking: '',
  on: 'Alerts are on for this device.',
  off: 'Get a phone or desktop alert when something needs you, even with Vaari closed.',
  blocked: 'Alerts are blocked for this site. Allow notifications in the browser’s site settings, then reload.',
  'ios-install': 'On iPhone, add Vaari to the Home Screen first (Share → Add to Home Screen), then turn alerts on there.',
  insecure: 'Alerts need a secure (https) address.',
  unsupported: 'This browser cannot show alerts. Use Chrome, Edge, Firefox or Safari 16.4+.',
};
