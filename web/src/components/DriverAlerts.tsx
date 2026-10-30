/** Driver page: one big switch so this phone rings when a job is added, removed, or at the start of the day. */
import { useMemo, useState } from 'react';
import { IconBell, IconBellOff } from '../shell/icons';
import { PUSH_HINT, usePush } from '../shell/push';

export default function DriverAlerts({ token }: { token: string }) {
  const target = useMemo(() => ({ kind: 'driver' as const, token }), [token]);
  const push = usePush(target);
  const [note, setNote] = useState<string | null>(null);
  if (push.state === 'checking' || push.state === 'unsupported' || push.state === 'insecure') return null;

  const test = async () => {
    setNote(null);
    const r = await push.test();
    if (r) setNote(r.sent > 0 ? 'Test sent. Your phone should ring now.' : 'The test did not reach this phone.');
  };

  return (
    <div className={`driver-alerts ${push.state === 'on' ? 'is-on' : ''}`} id="driver-alerts">
      {push.state === 'on' ? <IconBell /> : <IconBellOff />}
      <div className="driver-alerts-text">
        <b>{push.state === 'on' ? 'Job alerts are on' : 'Job alerts'}</b>
        <span>
          {push.state === 'on'
            ? 'This phone rings for new or removed jobs, and gets the job list each morning.'
            : push.state === 'off'
              ? 'Let this phone ring when a job is added or removed.'
              : PUSH_HINT[push.state]}
        </span>
        {push.error && (
          <span className="alerts-device-error" role="alert">
            {push.error}
          </span>
        )}
        {note && <span className="alerts-device-ok">{note}</span>}
      </div>
      {push.state === 'off' && (
        <button type="button" className="btn btn-primary" id="btn-driver-alerts-on" disabled={push.busy} onClick={() => void push.enable()}>
          {push.busy ? 'Turning on…' : 'Turn on'}
        </button>
      )}
      {push.state === 'on' && (
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button type="button" className="btn btn-secondary btn-sm" id="btn-driver-alerts-test" onClick={() => void test()}>
            Test
          </button>
          <button type="button" className="btn btn-ghost btn-sm" id="btn-driver-alerts-off" disabled={push.busy} onClick={() => void push.disable()}>
            Turn off
          </button>
        </div>
      )}
    </div>
  );
}
