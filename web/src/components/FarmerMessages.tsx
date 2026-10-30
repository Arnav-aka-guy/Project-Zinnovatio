/** Every message Vaari sent (or held back) for one request: SMS/WhatsApp to the farmer and alerts to the driver. */
import { useCallback, useEffect, useState } from 'react';
import { ApiError, getOutbox, retryOutbox } from '../api';
import type { OutboxItem } from '../types';
import { KIND_WORDS, STATUS_WORDS, channelWords, reasonWords, shortTime } from '../notify/words';

export default function FarmerMessages({ requestId, refreshKey }: { requestId: number; refreshKey?: string }) {
  const [items, setItems] = useState<OutboxItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await getOutbox({ request_id: requestId, limit: 30 });
      setItems(res.items.filter(i => i.audience === 'farmer' || i.audience === 'driver'));
      setError(null);
    } catch (e) {
      // Officers cannot see farmer messages: show nothing rather than an error.
      if (e instanceof ApiError && e.status === 403) setItems([]);
      else setError('Could not load messages.');
    }
  }, [requestId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    if (!items?.some(i => i.status === 'queued' || i.status === 'sending')) return;
    const id = window.setTimeout(() => void load(), 4000);
    return () => window.clearTimeout(id);
  }, [items, load]);

  const retry = async (id: number) => {
    setBusy(id);
    try {
      await retryOutbox(id);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send again.');
    } finally {
      setBusy(null);
    }
  };

  if (items === null && !error) return null;
  if (items && items.length === 0 && !error) return null;

  return (
    <div className="panel-card" id="farmer-messages">
      <h3>Messages sent</h3>
      {error && <div className="outcome-banner outcome-warning mb-2">{error}</div>}
      <ul className="msg-list">
        {(items ?? []).map(m => (
          <li key={m.id} className="msg-item" data-status={m.status} data-kind={m.kind}>
            <div className="msg-item-head">
              <span>
                <span className="msg-item-kind">{KIND_WORDS[m.kind] ?? m.kind}</span>
                {' · '}
                {m.audience === 'driver' ? 'to driver' : 'to farmer'} by {channelWords(m)}
              </span>
              <span className={`msg-status s-${m.status}`}>{STATUS_WORDS[m.status] ?? m.status}</span>
            </div>
            <div className="msg-item-body">{m.audience === 'driver' ? `${m.title ?? ''} — ${m.body}` : m.body}</div>
            <div className="msg-item-foot">
              <span>
                {shortTime(m.sent_at || m.created_at)}
                {m.status_reason && ` · ${reasonWords(m.status_reason)}`}
                {m.attempts > 1 && ` · ${m.attempts} tries`}
              </span>
              {(m.status === 'failed' || (m.status === 'skipped' && m.status_reason === 'no_devices')) && (
                <button type="button" className="btn btn-secondary btn-sm" disabled={busy === m.id} onClick={() => void retry(m.id)}>
                  {busy === m.id ? 'Sending…' : 'Send again'}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
