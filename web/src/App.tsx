import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink, Link, useLocation, useNavigate } from 'react-router-dom';
import PasscodeGate from './components/PasscodeGate';
import SignOutButton from './components/SignOutButton';
import AlertsBell from './components/AlertsBell';
import DeskPage from './pages/DeskPage';
import DriverPage from './pages/DriverPage';
import OfficerPage from './pages/OfficerPage';
import RecordPage from './pages/RecordPage';
import DriverPickerPage from './pages/DriverPickerPage';
import RecordPickerPage from './pages/RecordPickerPage';
import IntakePage from './pages/IntakePage';
import VoiceBookingPage from './pages/VoiceBookingPage';
import {
  IconCamera,
  IconChart,
  IconClose,
  IconDesk,
  IconDownload,
  IconMic,
  IconMore,
  IconOffline,
  IconReceipt,
  IconShare,
  IconSignOut,
  IconTractor,
  VaariMark,
} from './shell/icons';
import { useInstall, useOnline } from './shell/useInstall';

/** Driver and record links are opened by drivers and farmers: no staff menu there. */
const PUBLIC_PAGE = /^\/(driver|record)\/[^/]+/;

const PAGE_TITLES: Record<string, string> = {
  '/desk': 'Desk',
  '/intake': 'Register photo',
  '/voice': 'Voice booking',
  '/officer': 'Officer',
  '/driver': 'Driver links',
  '/record': 'Records',
};

const navClass = ({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`;
const tabClass = ({ isActive }: { isActive: boolean }) => `tabbar-item ${isActive ? 'active' : ''}`;

function OfflineBar() {
  const online = useOnline();
  if (online) return null;
  return (
    <div className="offline-bar" role="status">
      <IconOffline /> No signal. Saved screens still open; changes need a connection.
    </div>
  );
}

function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const install = useInstall();
  const [iosHelp, setIosHelp] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label="More"
        id="more-sheet"
        onClick={e => e.stopPropagation()}
      >
        <div className="sheet-grip" aria-hidden />
        <div className="sheet-head">
          <span className="sheet-title">More</span>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>
            <IconClose />
          </button>
        </div>
        <nav className="sheet-list" aria-label="More pages">
          <Link to="/driver" id="mnav-driver" className={`sheet-item ${pathname === '/driver' ? 'active' : ''}`} onClick={onClose}>
            <IconTractor />
            <span>
              Driver links<small>Open a machine's job list</small>
            </span>
          </Link>
          <Link to="/record" id="mnav-record" className={`sheet-item ${pathname === '/record' ? 'active' : ''}`} onClick={onClose}>
            <IconReceipt />
            <span>
              Service records<small>Finished jobs and their receipts</small>
            </span>
          </Link>
          {install.canPrompt && (
            <button type="button" id="btn-install-app" className="sheet-item" onClick={() => void install.prompt().then(onClose)}>
              <IconDownload />
              <span>
                Install Vaari<small>Add to home screen, opens full screen</small>
              </span>
            </button>
          )}
          {install.iosHint && (
            <button type="button" id="btn-install-ios" className="sheet-item" onClick={() => setIosHelp(v => !v)}>
              <IconDownload />
              <span>
                Install Vaari<small>Add to home screen on iPhone</small>
              </span>
            </button>
          )}
          {iosHelp && (
            <p className="sheet-help">
              Tap <IconShare /> <b>Share</b> in Safari, then <b>Add to Home Screen</b>.
            </p>
          )}
          <SignOutButton id="btn-sign-out-m" className="sheet-item">
            <IconSignOut />
            <span>Sign out</span>
          </SignOutButton>
        </nav>
      </div>
    </div>
  );
}

function TabBar() {
  const [more, setMore] = useState(false);
  const { pathname } = useLocation();
  const moreActive = pathname === '/driver' || pathname === '/record';
  return (
    <>
      <nav className="tabbar" aria-label="Main">
        <NavLink to="/desk" id="mnav-desk" className={tabClass}>
          <IconDesk />
          <span>Desk</span>
        </NavLink>
        <NavLink to="/voice" id="mnav-voice" className={tabClass}>
          <IconMic />
          <span>Voice</span>
        </NavLink>
        <NavLink to="/intake" id="mnav-intake" className={tabClass}>
          <IconCamera />
          <span>Register</span>
        </NavLink>
        <NavLink to="/officer" id="mnav-officer" className={tabClass}>
          <IconChart />
          <span>Officer</span>
        </NavLink>
        <button
          type="button"
          id="mnav-more"
          className={`tabbar-item ${moreActive || more ? 'active' : ''}`}
          aria-haspopup="dialog"
          aria-expanded={more}
          onClick={() => setMore(true)}
        >
          <IconMore />
          <span>More</span>
        </button>
      </nav>
      <MoreSheet open={more} onClose={() => setMore(false)} />
    </>
  );
}

function Shell() {
  const { pathname } = useLocation();
  const isPublic = PUBLIC_PAGE.test(pathname);
  const title = PAGE_TITLES[pathname] ?? '';

  const navigate = useNavigate();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  // A tapped alert asks an open Vaari window to show its screen.
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === 'vaari-open' && typeof e.data.url === 'string' && e.data.url.startsWith('/')) {
        navigate(e.data.url);
      }
    };
    navigator.serviceWorker?.addEventListener('message', onMessage);
    return () => navigator.serviceWorker?.removeEventListener('message', onMessage);
  }, [navigate]);

  return (
    <div className={`app-shell ${isPublic ? 'is-public' : 'has-tabbar'}`}>
      <header className="app-navbar">
        <div className="navbar-container">
          <div className="brand-group">
            <VaariMark size={28} />
            <span className="brand-name">Vaari</span>
            <span className="brand-phase">v0.1</span>
            {!isPublic && title && <span className="brand-page">{title}</span>}
          </div>
          {!isPublic && (
            <nav className="nav-links" aria-label="Main">
              <NavLink to="/desk" className={navClass} id="nav-desk">
                Desk
              </NavLink>
              <NavLink to="/intake" className={navClass} id="nav-intake">
                Register Intake
              </NavLink>
              <NavLink to="/voice" className={navClass} id="nav-voice">
                Voice booking
              </NavLink>
              <NavLink to="/officer" className={navClass} id="nav-officer">
                Officer
              </NavLink>
              <NavLink to="/driver" className={navClass} id="nav-driver">
                Driver View
              </NavLink>
              <NavLink to="/record" className={navClass} id="nav-record">
                Record View
              </NavLink>
              <SignOutButton />
            </nav>
          )}
          {!isPublic && <AlertsBell />}
        </div>
      </header>
      <OfflineBar />

      <main className="app-content">
        <Routes>
          <Route path="/" element={<Navigate to="/desk" replace />} />
          <Route
            path="/desk"
            element={
              <PasscodeGate>
                <DeskPage />
              </PasscodeGate>
            }
          />
          <Route
            path="/intake"
            element={
              <PasscodeGate>
                <IntakePage />
              </PasscodeGate>
            }
          />
          <Route
            path="/voice"
            element={
              <PasscodeGate>
                <VoiceBookingPage />
              </PasscodeGate>
            }
          />
          <Route
            path="/driver"
            element={
              <PasscodeGate>
                <DriverPickerPage />
              </PasscodeGate>
            }
          />
          <Route path="/driver/:machineToken" element={<DriverPage />} />
          <Route
            path="/officer"
            element={
              <PasscodeGate roles={['officer', 'operator']}>
                <OfficerPage />
              </PasscodeGate>
            }
          />
          <Route
            path="/record"
            element={
              <PasscodeGate>
                <RecordPickerPage />
              </PasscodeGate>
            }
          />
          <Route path="/record/:token" element={<RecordPage />} />
          <Route path="*" element={<Navigate to="/desk" replace />} />
        </Routes>
      </main>

      {!isPublic && <TabBar />}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
