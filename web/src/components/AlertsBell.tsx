/**
 * The bell in the top bar: alerts for this person's role (will miss, not served,
 * flagged jobs, failed farmer messages, locked accounts) and the switch that
 * turns on phone/desktop alerts for this device.
 *
 * Desktop: a dropdown under the bell. Phone: a bottom sheet.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { ApiError, getInbox, markAlertsRead } from '../api';
import type { Inbox, StaffAlert } from '../types';
import { IconBell, IconBellOff, IconCheck, IconClose } from '../shell/icons';
import { useIsPhone } from '../shell/useInstall';
import { PUSH_HINT, resyncPush, usePush } from '../shell/push';

const POLL_MS = 30_000;
const STAFF = { kind: 'staff' } as const;

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function setAppBadge(n: number) {
  const nav = navigator as Navigator & { setAppBadge?: (n?: number) => Promise<void>; clearAppBadge?: () => Promise<void> };
  try {
    if (n > 0) void nav.setAppBadge?.(n).catch(() => undefined);
    else void nav.clearAppBadge?.().catch(() => undefined);
  } catch {
    /* not supported */
  }
}

function DeviceAlerts() {
  const push = usePush(STAFF);
  const [tested, setTested] = useState<string | null>(null);
  if (push.state === 'checking') return null;

  const test = async () => {
    setTested(null);
    const r = await push.test();
    if (r) setTested(r.sent > 0 ? 'Sent. It should pop up in a few seconds.' : `Not delivered${r.detail ? ` (${r.detail})` : ''}.`);
  };

  return (
    <div className={`alerts-device ${push.state === 'on' ? 'is-on' : ''}`} id="alerts-device">
      <div className="alerts-device-text">
        <b>{push.state === 'on' ? 'Alerts on this device' : 'Alerts when Vaari is closed'}</b>
        <span>{PUSH_HINT[push.state]}</span>
        {push.error && (
          <span className="alerts-device-error" role="alert">
            {push.error}
          </span>
        )}
        {tested && <span className="alerts-device-ok">{tested}</span>}
      </div>
      <div className="alerts-device-actions">
        {push.state === 'off' && (
          <button type="button" className="btn btn-primary btn-sm" id="btn-alerts-on" disabled={push.busy} onClick={() => void push.enable()}>
            {push.busy ? 'Turning on…' : 'Turn on'}
          </button>
        )}
        {push.state === 'on' && (
          <>
            <button type="button" className="btn btn-secondary btn-sm" id="btn-alerts-test" onClick={() => void test()}>
              Send test
            </button>
            <button type="button" className="btn btn-ghost btn-sm" id="btn-alerts-off" disabled={push.busy} onClick={() => void push.disable()}>
              Turn off
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function AlertList({ inbox, onOpen }: { inbox: Inbox | null; onOpen: (a: StaffAlert) => void }) {
  if (!inbox) return <p className="alerts-empty">Loading…</p>;
  if (inbox.items.length === 0)
    return (
      <p className="alerts-empty" id="alerts-empty">
        <IconCheck /> Nothing needs you right now.
      </p>
    );
  return (
    <ul className="alerts-list" id="alerts-list">
      {inbox.items.map(a => (
        <li key={a.id}>
          <button
            type="button"
            className={`alert-item ${a.read ? '' : 'is-unread'} ${a.urgency === 'high' ? 'is-high' : ''}`}
            data-kind={a.kind}
            onClick={() => onOpen(a)}
          >
            <span className="alert-dot" aria-hidden />
            <span className="alert-text">
              <span className="alert-title">{a.title}</span>
              <span className="alert-body">{a.body}</span>
              <span className="alert-time">{timeAgo(a.created_at)}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function AlertsBell() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [hidden, setHidden] = useState(false);
  const [open, setOpen] = useState(false);
  const isPhone = useIsPhone();
  const navigate = useNavigate();
  const wrapRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await getInbox();
      setInbox(data);
      setHidden(false);
      setAppBadge(data.unread);
    } catch (e) {
      // Not signed in yet (the sign-in screen is showing): no bell.
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setHidden(true);
    }
  }, []);

  useEffect(() => {
    void load();
    void resyncPush(STAFF);
    const tick = () => document.visibilityState === 'visible' && void load();
    const id = window.setInterval(tick, POLL_MS);
    const onVisible = () => tick();
    const onSignIn = () => {
      void load();
      void resyncPush(STAFF);
    };
    const onMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === 'vaari-push') void load();
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('vaari-auth-changed', onSignIn);
    navigator.serviceWorker?.addEventListener('message', onMessage);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('vaari-auth-changed', onSignIn);
      navigator.serviceWorker?.removeEventListener('message', onMessage);
    };
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    const onDown = (e: MouseEvent) => {
      if (!isPhone && wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open, isPhone]);

  if (hidden) return null;
  const unread = inbox?.unread ?? 0;

  const openAlert = async (a: StaffAlert) => {
    setOpen(false);
    if (!a.read) {
      setInbox(prev => prev && { unread: Math.max(0, prev.unread - 1), items: prev.items.map(x => (x.id === a.id ? { ...x, read: true } : x)) });
      void markAlertsRead([a.id]).catch(() => undefined);
    }
    navigate(a.url || '/desk');
  };

  const readAll = async () => {
    await markAlertsRead('all').catch(() => undefined);
    await load();
  };

  const panel = (
    <>
      <div className="alerts-head">
        <span className="sheet-title">Alerts</span>
        <div className="alerts-head-actions">
          {unread > 0 && (
            <button type="button" className="btn btn-ghost btn-sm" id="btn-alerts-read-all" onClick={() => void readAll()}>
              Mark all read
            </button>
          )}
          <button type="button" className="icon-btn" aria-label="Close" onClick={() => setOpen(false)}>
            <IconClose />
          </button>
        </div>
      </div>
      <DeviceAlerts />
      <AlertList inbox={inbox} onOpen={a => void openAlert(a)} />
    </>
  );

  return (
    <div className="alerts-wrap" ref={wrapRef}>
      <button
        type="button"
        className={`icon-btn alerts-bell ${unread > 0 ? 'has-unread' : ''}`}
        id="btn-alerts"
        aria-label={unread > 0 ? `Alerts, ${unread} new` : 'Alerts'}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          setOpen(v => !v);
          if (!open) void load();
        }}
      >
        {inbox === null && hidden ? <IconBellOff /> : <IconBell />}
        {unread > 0 && (
          <span className="alerts-count" id="alerts-count">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open &&
        (isPhone ? (
          // On the body, so the top bar (sticky, blurred) cannot trap it under the tab bar.
          createPortal(
          <div className="sheet-overlay" onClick={() => setOpen(false)}>
            <div className="sheet alerts-sheet" role="dialog" aria-modal="true" aria-label="Alerts" id="alerts-panel" onClick={e => e.stopPropagation()}>
              <div className="sheet-grip" aria-hidden />
              {panel}
            </div>
          </div>,
          document.body,
          )
        ) : (
          <div className="alerts-pop" role="dialog" aria-label="Alerts" id="alerts-panel">
            {panel}
          </div>
        ))}
    </div>
  );
}
