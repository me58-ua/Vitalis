import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from './AuthContext';
import { currentUser, endSession, login } from '../api/auth';
import { errorMessage } from '../api/errors';
import { session } from '../api/session';
import type { User } from '../types/api';

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const [initializing, setInitializing] = useState(() => Boolean(session.read()));
  const [restoreError, setRestoreError] = useState('');
  const [restoreRevision, setRestoreRevision] = useState(0);
  const attempt = useRef(0);
  const locked = useRef(false);
  useEffect(() => session.subscribe(() => {
    if (!session.read()) setUser(null);
  }), []);
  useEffect(() => {
    if (!session.read()) return;
    const abort = new AbortController();
    const generation = session.generation();
    void currentUser(abort.signal).then(account => {
      if (!abort.signal.aborted && generation === session.generation()) setUser(account);
    }).catch((error: unknown) => {
      if (!abort.signal.aborted && session.read() && generation === session.generation()) setRestoreError(errorMessage(error));
    }).finally(() => { if (!abort.signal.aborted) setInitializing(false); });
    return () => abort.abort();
  }, [restoreRevision]);

  async function logout() {
    if (locked.current) return;
    locked.current = true; setBusy(true); setLogoutError('');
    const request = ++attempt.current;
    try {
      await endSession();
      if (request === attempt.current) { session.replace(null); setUser(null); }
    } catch (error: unknown) {
      if (request === attempt.current) setLogoutError(errorMessage(error));
    } finally {
      if (request === attempt.current) { locked.current = false; setBusy(false); }
    }
  }

  async function signIn(identifier: string, password: string) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setLogoutError('');
    const request = ++attempt.current;
    session.replace(null);
    setUser(null);
    try {
      const tokens = await login(identifier, password);
      if (request !== attempt.current) return;
      session.replace(tokens);
      const account = await currentUser();
      if (request === attempt.current) setUser(account);
    } catch (error: unknown) {
      if (request === attempt.current) session.replace(null);
      throw error;
    } finally {
      if (request === attempt.current) { setBusy(false); locked.current = false; }
    }
  }
  async function refreshUser() {
    const generation = session.generation();
    const account = await currentUser();
    if (generation === session.generation()) setUser(account);
  }
  return <AuthContext.Provider value={{ user, busy, logoutError, signIn, logout, refreshUser }}>
    {initializing ? <main className="section-container"><p role="status">Restaurando sesión…</p></main>
      : restoreError ? <main className="section-container"><h1>No se pudo restaurar la sesión</h1><p className="error-state" role="alert">{restoreError}</p><button className="button primary" onClick={() => { setRestoreError(''); setInitializing(true); setRestoreRevision(value => value + 1); }}>Reintentar</button><button className="button secondary" onClick={() => { session.replace(null); setUser(null); setRestoreError(''); navigate('/login', { replace: true }); }}>Ir a iniciar sesión</button></main>
      : children}
  </AuthContext.Provider>;
}
