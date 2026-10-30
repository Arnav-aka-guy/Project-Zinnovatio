/** Small stroke icons for the app shell (24px grid, currentColor). No icon library needed. */
import type { ReactNode } from 'react';

function Svg({ children, size = 24 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const IconDesk = () => (
  <Svg>
    <rect x="3" y="3" width="7.5" height="7.5" rx="1.8" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.8" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.8" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.8" />
  </Svg>
);
export const IconMic = () => (
  <Svg>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
  </Svg>
);
export const IconCamera = () => (
  <Svg>
    <path d="M4 8h3l1.6-2.4h6.8L17 8h3a1 1 0 0 1 1 1v9.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
    <circle cx="12" cy="13.3" r="3.4" />
  </Svg>
);
export const IconChart = () => (
  <Svg>
    <path d="M4 20V10M10 20V4M16 20v-7M21 20H3" />
  </Svg>
);
export const IconMore = () => (
  <Svg>
    <circle cx="5" cy="12" r="1.2" fill="currentColor" />
    <circle cx="12" cy="12" r="1.2" fill="currentColor" />
    <circle cx="19" cy="12" r="1.2" fill="currentColor" />
  </Svg>
);
export const IconTractor = () => (
  <Svg>
    <circle cx="7" cy="16" r="4" />
    <circle cx="18" cy="17.5" r="2.5" />
    <path d="M4 12V6h6l2 6h6.5a2 2 0 0 1 2 2v1M11 16h4.5M10 6v6" />
  </Svg>
);
export const IconReceipt = () => (
  <Svg>
    <path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" />
    <path d="M9 8h6M9 12h6" />
  </Svg>
);
export const IconDownload = () => (
  <Svg>
    <path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 20h14" />
  </Svg>
);
export const IconSignOut = () => (
  <Svg>
    <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M10 16l-4-4 4-4M6 12h10" />
  </Svg>
);
export const IconClose = () => (
  <Svg>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);
export const IconOffline = () => (
  <Svg size={18}>
    <path d="M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 4-2.4M19 13a10 10 0 0 0-3.2-2M2 9.5a15 15 0 0 1 4.3-2.7M22 9.5A15 15 0 0 0 11 5.1" />
    <circle cx="12" cy="20" r="0.6" fill="currentColor" />
  </Svg>
);
export const IconShare = () => (
  <Svg size={18}>
    <path d="M12 3v12M8 7l4-4 4 4M5 12v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7" />
  </Svg>
);

/** The Vaari mark (same drawing as the app icon). */
export function VaariMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" aria-hidden="true" focusable="false">
      <rect width="512" height="512" rx="120" fill="#15803d" />
      <g fill="#fff">
        <path d="M252 418c-4-80 0-170 8-268l12 1c-8 98-12 188-8 267z" />
        <path d="M254 330c-34-6-62-30-72-66 36 4 64 28 72 66zM262 330c34-6 62-30 72-66-36 4-64 28-72 66z" />
        <path d="M256 268c-34-6-62-30-72-66 36 4 64 28 72 66zM264 268c34-6 62-30 72-66-36 4-64 28-72 66z" />
        <path d="M258 206c-34-6-62-30-72-66 36 4 64 28 72 66zM266 206c34-6 62-30 72-66-36 4-64 28-72 66z" />
        <path d="M266 150c-22-22-26-58-6-86 18 30 20 62 6 86z" />
        <path d="M250 404c-40-8-80-36-96-78 46 6 82 34 96 78z" opacity=".85" />
      </g>
    </svg>
  );
}
export const IconBell = () => (
  <Svg>
    <path d="M6 16.5V11a6 6 0 1 1 12 0v5.5l1.5 2H4.5z" />
    <path d="M10 20.5a2.2 2.2 0 0 0 4 0" />
  </Svg>
);
export const IconBellOff = () => (
  <Svg>
    <path d="M8.2 5.6A6 6 0 0 1 18 11v4M6 11v5.5l-1.5 2H17M10 20.5a2.2 2.2 0 0 0 4 0M3 3l18 18" />
  </Svg>
);
export const IconCheck = () => (
  <Svg>
    <path d="M4.5 12.5l4.5 4.5 10.5-10.5" />
  </Svg>
);
