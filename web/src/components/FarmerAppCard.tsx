/**
 * Request details: how this farmer gets Vaari's messages. Nothing is sent by SMS or WhatsApp:
 * the farmer scans this QR code once, opens their own page, and taps "Turn on" so their phone
 * shows Vaari alerts.
 */
import { useCallback, useEffect, useState } from 'react';
import { ApiError, getFarmerLink, rotateFarmerLink } from '../api';
import type { FarmerLinkOut } from '../types';
import QrCode from './QrCode';

export default function FarmerAppCard({ requestId }: { requestId: number }) {
  const [link, setLink] = useState<FarmerLinkOut | null>(null);
  const [hidden, setHidden] = useState(false);
  const [big, setBig] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirmNew, setConfirmNew] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLink(await getFarmerLink(requestId));
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 403 || e.status === 401)) setHidden(true);
      else setError('Could not load the farmer link.');
    }
  }, [requestId]);

  useEffect(() => {
    void load();
  }, [load]);

  // While the QR is on screen, check every few seconds whether the farmer has turned alerts on.
  useEffect(() => {
    if (!big) return;
    const id = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(id);
  }, [big, load]);

  if (hidden) return null;
  const url = link ? link.url || `${window.location.origin}${link.path}` : '';

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the link is visible to select */
    }
  };

  const renew = async () => {
    setConfirmNew(false);
    try {
      setLink(await rotateFarmerLink(requestId));
    } catch {
      setError('Could not make a new link.');
    }
  };

  return (
    <div className="panel-card farmer-app-card" id="farmer-app-card">
      <h3>Farmer app</h3>
      {error && <div className="outcome-banner outcome-warning mb-2">{error}</div>}
      {link && (
        <>
          <p className={`farmer-app-state ${link.devices > 0 ? 'is-on' : ''}`} id="farmer-app-state">
            {link.devices > 0
              ? `Alerts are on for ${link.devices} phone${link.devices === 1 ? '' : 's'}. Every change reaches the farmer in Vaari.`
              : 'The farmer has not turned on alerts yet. Show them this QR code: they scan it, then tap “Turn on”.'}
          </p>
          <div className="farmer-app-row">
            <button type="button" className="farmer-app-qr" onClick={() => setBig(true)} aria-label="Show the QR code large">
              <QrCode text={url} size={112} label="QR code for the farmer's Vaari page" />
            </button>
            <div className="farmer-app-actions">
              <button type="button" className="btn btn-primary btn-sm" id="btn-farmer-qr" onClick={() => setBig(true)}>
                Show QR to farmer
              </button>
              <button type="button" className="btn btn-secondary btn-sm" id="btn-farmer-copy" onClick={() => void copy()}>
                {copied ? '✓ Copied' : 'Copy link'}
              </button>
              <a className="btn btn-ghost btn-sm" id="farmer-app-open" href={link.path} target="_blank" rel="noopener noreferrer">
                Open farmer page
              </a>
              {!confirmNew ? (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirmNew(true)}>
                  New link…
                </button>
              ) : (
                <span className="farmer-app-confirm">
                  Old link and its phones stop working.{' '}
                  <button type="button" className="link-btn" id="btn-farmer-new-link" onClick={() => void renew()}>
                    Make new link
                  </button>{' '}
                  <button type="button" className="link-btn" onClick={() => setConfirmNew(false)}>
                    Keep
                  </button>
                </span>
              )}
            </div>
          </div>
          {link.last_opened_at && (
            <p className="farmer-app-note">
              Farmer last opened their page {new Date(link.last_opened_at).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })}.
            </p>
          )}
        </>
      )}
      {big && link && (
        <div className="qr-overlay" role="dialog" aria-modal="true" aria-label="QR code for the farmer" id="farmer-qr-overlay" onClick={() => setBig(false)}>
          <div className="qr-sheet" onClick={e => e.stopPropagation()}>
            <p className="qr-title">ਆਪਣੇ ਫ਼ੋਨ ਨਾਲ ਸਕੈਨ ਕਰੋ</p>
            <p className="qr-sub">Scan with your phone camera</p>
            <QrCode text={url} size={300} label="QR code for the farmer's Vaari page" />
            <p className="qr-steps">
              ਫਿਰ <b>“ਚਾਲੂ ਕਰੋ”</b> ਦਬਾਓ। ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਦੇ ਸਾਰੇ ਸੁਨੇਹੇ ਤੁਹਾਡੇ ਫ਼ੋਨ &apos;ਤੇ ਆਉਣਗੇ।
              <br />
              <span>Then tap “Turn on”. Every message about the machine turn comes to your phone.</span>
            </p>
            <p className={`farmer-app-state ${link.devices > 0 ? 'is-on' : ''}`} id="farmer-qr-state">
              {link.devices > 0 ? '✓ Alerts are on for this farmer' : 'Waiting for the farmer to turn on alerts…'}
            </p>
            <button type="button" className="btn btn-secondary" onClick={() => setBig(false)}>
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
