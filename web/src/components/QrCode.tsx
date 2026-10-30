/** A QR code as a crisp SVG (scales to any size, prints well). */
import { useMemo } from 'react';
import { qrMatrix } from '../shell/qr';

export default function QrCode({ text, size = 200, label }: { text: string; size?: number; label?: string }) {
  const { path, n } = useMemo(() => {
    const m = qrMatrix(text);
    let d = '';
    m.forEach((row, y) =>
      row.forEach((dark, x) => {
        if (dark) d += `M${x + 4} ${y + 4}h1v1h-1z`;
      }),
    );
    return { path: d, n: m.length + 8 };
  }, [text]);
  return (
    <svg
      className="qr-code"
      width={size}
      height={size}
      viewBox={`0 0 ${n} ${n}`}
      shapeRendering="crispEdges"
      role="img"
      aria-label={label ?? 'QR code'}
      data-qr-text={text}
    >
      <rect width={n} height={n} fill="#fff" />
      <path d={path} fill="#0f172a" />
    </svg>
  );
}
