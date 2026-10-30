import { useEffect, useState, type ReactNode } from 'react';
import { getSessionToken, logout } from '../api';

interface Props {
  id?: string;
  className?: string;
  children?: ReactNode;
}

/** Shown only when a staff account is signed in (production mode). */
export default function SignOutButton({ id = 'btn-sign-out', className = 'nav-link', children = 'Sign out' }: Props) {
  const [signedIn, setSignedIn] = useState(!!getSessionToken());

  useEffect(() => {
    const update = () => setSignedIn(!!getSessionToken());
    window.addEventListener('vaari-auth-changed', update);
    return () => window.removeEventListener('vaari-auth-changed', update);
  }, []);

  if (!signedIn) return null;
  return (
    <button
      id={id}
      className={className}
      type="button"
      onClick={async () => {
        await logout().catch(() => undefined);
        window.dispatchEvent(new Event('vaari-auth-changed'));
        window.location.reload();
      }}
    >
      {children}
    </button>
  );
}
