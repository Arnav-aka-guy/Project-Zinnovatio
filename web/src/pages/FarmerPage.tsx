/**
 * The farmer's own page: /farmer/<token>. Punjabi first, English on a tap.
 *
 * Every message about the farmer's machine turn arrives here, and on their phone
 * as a Vaari alert once they tap "Turn on". Nothing is sent by SMS or WhatsApp.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ApiError, getFarmerPage, markFarmerRead } from '../api';
import type { FarmerBooking, FarmerMessage, FarmerPageData } from '../types';
import { IconBell, IconBellOff, IconCheck } from '../shell/icons';
import { usePush, type PushState } from '../shell/push';

type Lang = 'pa' | 'en';

const T = {
  pa: {
    title: 'ਮੇਰੀ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ',
    alertsOff: 'ਫ਼ੋਨ ’ਤੇ ਸੁਨੇਹੇ ਚਾਲੂ ਕਰੋ',
    alertsOffSub: 'ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਪੱਕੀ ਹੋਣ, ਬਦਲਣ ਜਾਂ ਕੰਮ ਸ਼ੁਰੂ ਹੋਣ ’ਤੇ ਤੁਹਾਡਾ ਫ਼ੋਨ ਵੱਜੇਗਾ।',
    turnOn: 'ਚਾਲੂ ਕਰੋ',
    turningOn: 'ਚਾਲੂ ਹੋ ਰਿਹਾ…',
    alertsOn: 'ਸੁਨੇਹੇ ਚਾਲੂ ਹਨ',
    alertsOnSub: 'ਹਰ ਸੁਨੇਹਾ ਇਸ ਫ਼ੋਨ ’ਤੇ ਆਵੇਗਾ।',
    test: 'ਟੈਸਟ',
    testSent: 'ਟੈਸਟ ਸੁਨੇਹਾ ਭੇਜਿਆ। ਫ਼ੋਨ ਹੁਣੇ ਵੱਜੇਗਾ।',
    testFailed: 'ਟੈਸਟ ਸੁਨੇਹਾ ਨਹੀਂ ਪਹੁੰਚਿਆ।',
    off: 'ਬੰਦ ਕਰੋ',
    blocked: 'ਇਸ ਫ਼ੋਨ ’ਤੇ ਸੁਨੇਹੇ ਰੋਕੇ ਹੋਏ ਹਨ। ਬ੍ਰਾਊਜ਼ਰ ਦੀ ਸੈਟਿੰਗ ਵਿੱਚ ਇਸ ਸਾਈਟ ਲਈ Notifications ਚਾਲੂ ਕਰੋ।',
    iosInstall: 'iPhone ’ਤੇ: ਹੇਠਾਂ Share ਦਬਾਓ, ਫਿਰ “Add to Home Screen”। ਫਿਰ ਹੋਮ ਸਕਰੀਨ ਤੋਂ ਵਾਰੀ ਖੋਲ੍ਹ ਕੇ ਚਾਲੂ ਕਰੋ।',
    unsupported: 'ਇਹ ਬ੍ਰਾਊਜ਼ਰ ਸੁਨੇਹੇ ਨਹੀਂ ਦਿਖਾ ਸਕਦਾ। Chrome ਵਿੱਚ ਖੋਲ੍ਹੋ। ਸੁਨੇਹੇ ਇਸ ਪੰਨੇ ’ਤੇ ਫਿਰ ਵੀ ਮਿਲਣਗੇ।',
    bookings: 'ਮੇਰੀਆਂ ਬੁਕਿੰਗਾਂ',
    noBookings: 'ਹਾਲੇ ਕੋਈ ਬੁਕਿੰਗ ਨਹੀਂ।',
    messages: 'ਸੁਨੇਹੇ',
    noMessages: 'ਹਾਲੇ ਕੋਈ ਸੁਨੇਹਾ ਨਹੀਂ।',
    acres: 'ਏਕੜ',
    job: 'ਵਾਰੀ ਨੰ.',
    code: 'ਕੰਮ ਪੂਰਾ ਹੋਣ ’ਤੇ ਡਰਾਈਵਰ ਨੂੰ ਇਹ ਕੋਡ ਦੱਸੋ',
    record: 'ਕੰਮ ਦਾ ਰਿਕਾਰਡ ਦੇਖੋ',
    deadline: 'ਆਖ਼ਰੀ ਤਾਰੀਖ਼',
    call: 'ਕੇਂਦਰ ਨੂੰ ਫ਼ੋਨ ਕਰੋ',
    loading: 'ਖੁੱਲ੍ਹ ਰਿਹਾ ਹੈ…',
    expired: 'ਇਹ ਲਿੰਕ ਬੰਦ ਹੋ ਗਿਆ ਹੈ। ਨਵੇਂ ਲਿੰਕ ਲਈ ਕੇਂਦਰ ’ਤੇ ਪੁੱਛੋ।',
    notFound: 'ਇਹ ਲਿੰਕ ਸਹੀ ਨਹੀਂ ਹੈ। ਕੇਂਦਰ ’ਤੇ QR ਕੋਡ ਦੁਬਾਰਾ ਸਕੈਨ ਕਰੋ।',
    offline: 'ਇੰਟਰਨੈੱਟ ਨਹੀਂ ਹੈ। ਥੋੜ੍ਹੀ ਦੇਰ ਬਾਅਦ ਦੁਬਾਰਾ ਖੋਲ੍ਹੋ।',
    retry: 'ਦੁਬਾਰਾ',
    failed: 'ਚਾਲੂ ਨਹੀਂ ਹੋ ਸਕਿਆ। ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।',
    justNow: 'ਹੁਣੇ',
    minAgo: 'ਮਿੰਟ ਪਹਿਲਾਂ',
    hAgo: 'ਘੰਟੇ ਪਹਿਲਾਂ',
  },
  en: {
    title: 'My machine turn',
    alertsOff: 'Turn on messages on this phone',
    alertsOffSub: 'Your phone rings when your machine turn is booked, changed, or the work starts.',
    turnOn: 'Turn on',
    turningOn: 'Turning on…',
    alertsOn: 'Messages are on',
    alertsOnSub: 'Every message will come to this phone.',
    test: 'Test',
    testSent: 'Test sent. Your phone should ring now.',
    testFailed: 'The test did not reach this phone.',
    off: 'Turn off',
    blocked: 'Messages are blocked on this phone. Allow Notifications for this site in the browser settings.',
    iosInstall: 'On iPhone: tap Share, then “Add to Home Screen”. Open Vaari from the Home Screen and turn messages on there.',
    unsupported: 'This browser cannot show alerts. Open the link in Chrome. Messages still appear on this page.',
    bookings: 'My bookings',
    noBookings: 'No bookings yet.',
    messages: 'Messages',
    noMessages: 'No messages yet.',
    acres: 'acres',
    job: 'Job no.',
    code: 'When the work is done, tell the driver this code',
    record: 'See the work record',
    deadline: 'Last date',
    call: 'Call the centre',
    loading: 'Opening…',
    expired: 'This link has been turned off. Ask the centre for a new one.',
    notFound: 'This link is not right. Scan the QR code at the centre again.',
    offline: 'No internet. Open this page again in a little while.',
    retry: 'Try again',
    failed: 'Could not turn on. Please try again.',
    justNow: 'just now',
    minAgo: 'min ago',
    hAgo: 'h ago',
  },
} as const;

const STATUS: Record<string, { pa: string; en: string; tone: string }> = {
  needs_info: { pa: 'ਵਾਢੀ ਦੀ ਤਾਰੀਖ਼ ਚਾਹੀਦੀ', en: 'Harvest date needed', tone: 'warn' },
  open: { pa: 'ਵਾਰੀ ਲੱਗ ਰਹੀ ਹੈ', en: 'Being planned', tone: 'info' },
  scheduled: { pa: 'ਵਾਰੀ ਪੱਕੀ', en: 'Booked', tone: 'ok' },
  in_progress: { pa: 'ਕੰਮ ਚੱਲ ਰਿਹਾ', en: 'Work in progress', tone: 'info' },
  done: { pa: 'ਕੰਮ ਪੂਰਾ', en: 'Done', tone: 'ok' },
  will_miss: { pa: 'ਹਾਲੇ ਮਸ਼ੀਨ ਖ਼ਾਲੀ ਨਹੀਂ', en: 'No machine free yet', tone: 'bad' },
  cancelled: { pa: 'ਰੱਦ', en: 'Cancelled', tone: 'muted' },
};

const SERVICE_PA: Record<string, string> = {
  super_seeder: 'ਸੁਪਰ ਸੀਡਰ',
  happy_seeder: 'ਹੈਪੀ ਸੀਡਰ',
  baler: 'ਬੇਲਰ',
  mulcher: 'ਮਲਚਰ',
};

const MONTHS_PA = ['ਜਨਵਰੀ', 'ਫ਼ਰਵਰੀ', 'ਮਾਰਚ', 'ਅਪ੍ਰੈਲ', 'ਮਈ', 'ਜੂਨ', 'ਜੁਲਾਈ', 'ਅਗਸਤ', 'ਸਤੰਬਰ', 'ਅਕਤੂਬਰ', 'ਨਵੰਬਰ', 'ਦਸੰਬਰ'];
const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function fmtDate(iso: string | null, lang: Lang): string {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${(lang === 'pa' ? MONTHS_PA : MONTHS_EN)[m - 1]}`;
}

function ago(iso: string, lang: Lang): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return T[lang].justNow;
  if (s < 3600) return `${Math.floor(s / 60)} ${T[lang].minAgo}`;
  if (s < 86400) return `${Math.floor(s / 3600)} ${T[lang].hAgo}`;
  const d = new Date(iso);
  return `${d.getDate()} ${(lang === 'pa' ? MONTHS_PA : MONTHS_EN)[d.getMonth()]}`;
}

function AlertsCard({ token, lang }: { token: string; lang: Lang }) {
  const target = useMemo(() => ({ kind: 'farmer' as const, token }), [token]);
  const push = usePush(target);
  const [note, setNote] = useState<string | null>(null);
  const t = T[lang];
  if (push.state === 'checking') return null;

  const hint: Partial<Record<PushState, string>> = {
    blocked: t.blocked,
    'ios-install': t.iosInstall,
    unsupported: t.unsupported,
    insecure: t.unsupported,
  };
  const test = async () => {
    setNote(null);
    const r = await push.test();
    if (r) setNote(r.sent > 0 ? t.testSent : t.testFailed);
  };

  if (push.state === 'on') {
    return (
      <section className="fa-alerts is-on" id="farmer-alerts">
        <IconBell />
        <div className="fa-alerts-text">
          <b>{t.alertsOn}</b>
          <span>{t.alertsOnSub}</span>
          {note && <span className="fa-note">{note}</span>}
        </div>
        <div className="fa-alerts-actions">
          <button type="button" className="btn btn-secondary btn-sm" id="btn-farmer-alerts-test" onClick={() => void test()}>
            {t.test}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" id="btn-farmer-alerts-off" disabled={push.busy} onClick={() => void push.disable()}>
            {t.off}
          </button>
        </div>
      </section>
    );
  }
  if (push.state === 'off') {
    return (
      <section className="fa-alerts" id="farmer-alerts">
        <div className="fa-alerts-head">
          <IconBellOff />
          <div className="fa-alerts-text">
            <b>{t.alertsOff}</b>
            <span>{t.alertsOffSub}</span>
          </div>
        </div>
        <button type="button" className="btn btn-primary fa-big-btn" id="btn-farmer-alerts-on" disabled={push.busy} onClick={() => void push.enable()}>
          {push.busy ? t.turningOn : t.turnOn}
        </button>
        {push.error && (
          <p className="fa-error" role="alert">
            {t.failed}
            {lang === 'pa' && <small> ({push.error})</small>}
            {lang === 'en' && <small> {push.error}</small>}
          </p>
        )}
      </section>
    );
  }
  return (
    <section className="fa-alerts is-hint" id="farmer-alerts">
      <IconBellOff />
      <div className="fa-alerts-text">
        <span>{hint[push.state]}</span>
      </div>
    </section>
  );
}

function BookingCard({ b, lang }: { b: FarmerBooking; lang: Lang }) {
  const t = T[lang];
  const st = STATUS[b.slot?.status === 'in_progress' ? 'in_progress' : b.status] ?? { pa: b.status, en: b.status, tone: 'muted' };
  const service = lang === 'pa' ? SERVICE_PA[b.service_type] ?? b.service_name : b.service_name;
  return (
    <article className="fa-booking" data-status={b.status} id={`farmer-booking-${b.id}`}>
      <div className="fa-booking-top">
        <div>
          <div className="fa-booking-service">{service}</div>
          <div className="fa-booking-sub">
            {b.village} · {b.acres} {t.acres}
          </div>
        </div>
        <span className={`fa-chip t-${st.tone}`}>{st[lang]}</span>
      </div>
      {b.slot && b.status !== 'cancelled' && (
        <div className="fa-booking-slot">
          <div className="fa-date">{fmtDate(b.slot.service_date, lang)}</div>
          <div className="fa-booking-sub">
            {b.slot.machine} · {t.job} {b.slot.seq}
          </div>
        </div>
      )}
      {!b.slot && b.deadline_date && b.status !== 'cancelled' && (
        <div className="fa-booking-sub">
          {t.deadline}: {fmtDate(b.deadline_date, lang)}
        </div>
      )}
      {b.slot?.service_code && (
        <div className="fa-code">
          <span>{t.code}</span>
          <b className="fa-code-digits">{b.slot.service_code}</b>
        </div>
      )}
      {b.record_path && (
        <a className="btn btn-secondary fa-record" href={b.record_path}>
          {t.record}
        </a>
      )}
    </article>
  );
}

function MessageItem({ m, lang }: { m: FarmerMessage; lang: Lang }) {
  const inner = (
    <>
      <span className="alert-dot" aria-hidden />
      <span className="alert-text">
        <span className="alert-title">{m.title}</span>
        <span className="alert-body">{m.body}</span>
        <span className="alert-time">{ago(m.created_at, lang)}</span>
      </span>
    </>
  );
  const cls = `alert-item ${m.read ? '' : 'is-unread'}`;
  return (
    <li>
      {m.url ? (
        <a className={cls} href={m.url} data-kind={m.kind}>
          {inner}
        </a>
      ) : (
        <div className={cls} data-kind={m.kind}>
          {inner}
        </div>
      )}
    </li>
  );
}

export default function FarmerPage() {
  const { token = '' } = useParams<{ token: string }>();
  const [data, setData] = useState<FarmerPageData | null>(null);
  const [error, setError] = useState<'expired' | 'notFound' | 'offline' | null>(null);
  const [lang, setLang] = useState<Lang | null>(null);
  const readTimer = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await getFarmerPage(token);
      setData(d);
      setError(null);
      setLang(prev => prev ?? (localStorageGet('vaari_farmer_lang') as Lang | null) ?? d.lang);
      if (d.unread > 0) {
        if (readTimer.current) window.clearTimeout(readTimer.current);
        // Seen for a moment: mark as read (the unread dots stay until the next refresh).
        readTimer.current = window.setTimeout(() => void markFarmerRead(token, 'all').catch(() => undefined), 2500);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 410) setError('expired');
      else if (e instanceof ApiError && e.status === 404) setError('notFound');
      else setError('offline');
    }
  }, [token]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => document.visibilityState === 'visible' && void load(), 60_000);
    const onVisible = () => document.visibilityState === 'visible' && void load();
    const onMessage = (e: MessageEvent) => e.data?.type === 'vaari-push' && void load();
    document.addEventListener('visibilitychange', onVisible);
    navigator.serviceWorker?.addEventListener('message', onMessage);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
      navigator.serviceWorker?.removeEventListener('message', onMessage);
      if (readTimer.current) window.clearTimeout(readTimer.current);
    };
  }, [load]);

  // "Add to Home Screen" opens this page, not the staff desk.
  useEffect(() => {
    const link = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
    if (!link) return;
    const before = link.href;
    link.href = `/api/farmer/${encodeURIComponent(token)}/manifest.webmanifest`;
    const title = document.title;
    document.title = 'Vaari · ਵਾਰੀ';
    return () => {
      link.href = before;
      document.title = title;
    };
  }, [token]);

  const l: Lang = lang ?? data?.lang ?? 'pa';
  const t = T[l];
  const switchLang = (next: Lang) => {
    setLang(next);
    localStorageSet('vaari_farmer_lang', next);
  };

  return (
    <div className="farmer-page" id="farmer-page" lang={l === 'pa' ? 'pa' : 'en'}>
      <div className="fa-top">
        <h1>{t.title}</h1>
        <div className="fa-lang" role="group" aria-label="Language">
          <button type="button" className={l === 'pa' ? 'active' : ''} aria-pressed={l === 'pa'} onClick={() => switchLang('pa')}>
            ਪੰਜਾਬੀ
          </button>
          <button type="button" className={l === 'en' ? 'active' : ''} aria-pressed={l === 'en'} onClick={() => switchLang('en')} id="btn-farmer-lang-en">
            English
          </button>
        </div>
      </div>

      {error ? (
        <section className="fa-empty" id="farmer-error" role="alert">
          <p>{t[error]}</p>
          {error === 'offline' && (
            <button type="button" className="btn btn-secondary" onClick={() => void load()}>
              {t.retry}
            </button>
          )}
        </section>
      ) : !data ? (
        <p className="fa-empty">{t.loading}</p>
      ) : (
        <>
          <AlertsCard token={token} lang={l} />

          <section className="fa-section">
            <h2>{t.bookings}</h2>
            {data.bookings.length === 0 ? (
              <p className="fa-empty">{t.noBookings}</p>
            ) : (
              data.bookings.map(b => <BookingCard key={b.id} b={b} lang={l} />)
            )}
          </section>

          <section className="fa-section">
            <h2>
              {t.messages}
              {data.unread > 0 && <span className="alerts-count fa-count">{data.unread}</span>}
            </h2>
            {data.messages.length === 0 ? (
              <p className="fa-empty">
                <IconCheck /> {t.noMessages}
              </p>
            ) : (
              <ul className="alerts-list fa-messages" id="farmer-messages-list">
                {data.messages.map(m => (
                  <MessageItem key={m.id} m={m} lang={l} />
                ))}
              </ul>
            )}
          </section>

          <a className="btn btn-secondary fa-call" href={`tel:+91${data.centre.phone}`} id="btn-farmer-call">
            {t.call} · {data.centre.name}
          </a>
        </>
      )}
    </div>
  );
}

// Browser storage can be missing or blocked; the page works without it.
function localStorageGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function localStorageSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}
