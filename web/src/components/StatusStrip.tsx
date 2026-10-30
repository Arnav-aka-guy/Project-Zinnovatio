import { useEffect, useState } from 'react';
import { getHealth } from '../api';
import Badge from './Badge';
import type { Health } from '../types';

export default function StatusStrip() {
  const [health, setHealth] = useState<Health | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  const fetchStatus = async () => {
    try {
      const data = await getHealth();
      setHealth(data);
      setUnreachable(false);
    } catch {
      setUnreachable(true);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  if (unreachable) {
    return (
      <div className="status-strip status-strip-down" id="status-strip" role="region" aria-label="System Status">
        <div className="status-strip-inner">
          <span className="status-dot dot-error" />
          <strong className="status-label-down">Server not reachable</strong>
        </div>
      </div>
    );
  }

  const dbStatus = health?.database === 'connected' ? 'ok' : (health?.database || 'down');
  const dbTone = dbStatus === 'ok' ? 'pill-green' : 'pill-red';

  const readerRaw = health?.reader || 'not_built';
  const readerStatus =
    readerRaw === 'hosted'
      ? 'ok'
      : readerRaw === 'mock'
      ? 'mock'
      : readerRaw === 'down'
      ? 'down'
      : 'not built';
  const readerTone =
    readerStatus === 'ok'
      ? 'pill-green'
      : readerStatus === 'mock'
      ? 'pill-amber'
      : readerStatus === 'down'
      ? 'pill-red'
      : 'pill-grey';

  // Every message goes through Vaari itself (farmer page, bell, phone alerts); no SMS or WhatsApp.
  const msgStatus = health?.notifications ? (health.notifications.worker ? 'in-app' : 'in-app (sender off)') : health?.messaging || 'in-app';
  const msgTone = health?.notifications ? (health.notifications.worker ? 'pill-green' : 'pill-amber') : 'pill-grey';

  const satStatus = health?.satellite === 'live' ? 'ok' : health?.satellite === 'mock' ? 'mock' : 'disabled';
  const satTone = satStatus === 'ok' ? 'pill-green' : satStatus === 'mock' ? 'pill-amber' : 'pill-grey';

  return (
    <div className="status-strip" id="status-strip" role="region" aria-label="System Status">
      <div className="status-strip-inner">
        {health ? (
          <>
            <div className="status-item">
              <span className="status-dot dot-ok" />
              <span className="status-label">System: <strong>{health.status}</strong></span>
            </div>

            <div className={`dep-pill ${dbTone}`} id="dep-pill-db">
              <span className="dep-name">Database:</span>
              <span className="dep-val">{dbStatus}</span>
            </div>

            <div className={`dep-pill ${readerTone}`} id="dep-pill-reader">
              <span className="dep-name">Reader:</span>
              <span className="dep-val">{readerStatus}</span>
            </div>

            <div className={`dep-pill ${msgTone}`} id="dep-pill-messaging">
              <span className="dep-name">Messaging:</span>
              <span className="dep-val">{msgStatus}</span>
            </div>

            <div className={`dep-pill ${satTone}`} id="dep-pill-satellite">
              <span className="dep-name">Satellite:</span>
              <span className="dep-val">{satStatus}</span>
            </div>

            {health.demo_clock ? (
              <Badge name="demo clock" detail={health.today} id="demo-clock-badge" />
            ) : (
              <div className="status-item text-muted text-xs">
                <span>Today: {health.today}</span>
              </div>
            )}
          </>
        ) : (
          <div className="status-item">
            <span className="status-label">Checking system status…</span>
          </div>
        )}
      </div>
    </div>
  );
}
