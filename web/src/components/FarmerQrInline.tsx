/** After a booking: the farmer scans this to get every message on their own phone in Vaari. */
import { useEffect, useState } from 'react';
import { getFarmerLink } from '../api';
import QrCode from './QrCode';

export default function FarmerQrInline({ requestId }: { requestId: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    getFarmerLink(requestId)
      .then(l => alive && setUrl(l.url || `${window.location.origin}${l.path}`))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [requestId]);
  if (!url) return null;
  return (
    <div className="farmer-qr-inline" id="farmer-qr-inline">
      <QrCode text={url} size={168} label="QR code for the farmer's Vaari page" />
      <p>
        <b>ਸੁਨੇਹੇ ਆਪਣੇ ਫ਼ੋਨ ’ਤੇ ਲੈਣ ਲਈ ਇਹ ਸਕੈਨ ਕਰੋ, ਫਿਰ “ਚਾਲੂ ਕਰੋ” ਦਬਾਓ।</b>
        <br />
        Scan this to get every message on your phone, then tap “Turn on”.
      </p>
    </div>
  );
}
