/** Officer view: are Vaari alerts reaching phones? Counts only, no farmer details. Nothing goes by SMS or WhatsApp. */
import { useEffect, useState } from 'react';
import { getNotifySummary } from '../api';
import type { NotificationStatus, NotifySummary } from '../types';
import { STATUS_WORDS, shortTime } from '../notify/words';

const ORDER: NotificationStatus[] = ['sent', 'simulated', 'queued', 'skipped', 'failed'];

function Cell({ title, counts, hint }: { title: string; counts?: Partial<Record<NotificationStatus, number>>; hint?: string }) {
  const shown = ORDER.filter(s => (counts?.[s] ?? 0) > 0);
  return (
    <div className="delivery-cell">
      <h4>{title}</h4>
      {shown.length === 0 ? (
        <p className="text-muted" style={{ margin: 0, fontSize: '0.82rem' }}>
          Nothing in the last 7 days
        </p>
      ) : (
        <dl>
          {shown.map(s => (
            <div key={s} style={{ display: 'contents' }}>
              <dt>{STATUS_WORDS[s]}</dt>
              <dd className={s === 'failed' ? 'text-danger' : undefined}>{counts?.[s]}</dd>
            </div>
          ))}
        </dl>
      )}
      {hint && <p className="delivery-hint">{hint}</p>}
    </div>
  );
}

export default function DeliveryCard() {
  const [data, setData] = useState<NotifySummary | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getNotifySummary()
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  if (failed || !data) return null;
  return (
    <section className="card" id="delivery-card">
      <div className="card-header">
        <div>
          <h2>Message delivery</h2>
          <p className="card-subtitle">
            Every message is sent inside Vaari: the farmer&apos;s page, the staff bell, and phone alerts. No SMS or
            WhatsApp.
            {data.quiet_hours ? ` Farmers' phones are not woken between ${data.quiet_hours.replace('-', ':00 and ')}:00.` : ''}
          </p>
        </div>
      </div>
      <div className="delivery-grid">
        <Cell
          title="To farmers (phone alerts)"
          counts={data.last_7_days.farmer}
          hint={data.devices.farmer === 0 ? 'No farmer phone has alerts on yet. Show the farmer their QR code.' : undefined}
        />
        <Cell
          title="To staff (phone alerts)"
          counts={data.last_7_days.staff}
          hint={data.devices.staff === 0 ? 'No staff device has alerts on yet. Use the bell, then Turn on.' : undefined}
        />
        <Cell
          title="To drivers (job alerts)"
          counts={data.last_7_days.driver}
          hint={data.devices.driver === 0 ? 'No driver phone has alerts on yet. Drivers turn them on from their link.' : undefined}
        />
      </div>
      <p className="delivery-note">
        Phones and computers with alerts on: {data.devices.farmer} farmer, {data.devices.staff} staff,{' '}
        {data.devices.driver} driver.
        {data.worker_running
          ? data.worker_last_run_at
            ? ` Sender last ran ${shortTime(data.worker_last_run_at)}.`
            : ' Sender is running.'
          : ' The sender is not running on this server, so nothing goes out.'}
      </p>
    </section>
  );
}
