import { useEffect, useRef, useState, type ReactNode } from 'react';
import { AuthContext } from './AuthContext';
import { currentUser, login } from '../api/auth';
import { session } from '../api/session';
import type { User } from '../types/api';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const attempt = useRef(0);
  const locked = useRef(false);
  useEffect(() => session.subscribe(() => {
    if (!session.read()) setUser(null);
  }), []);

  function logout() {
    attempt.current += 1;
    locked.current = false;
    session.replace(null);
    setUser(null);
    setBusy(false);
  }

  async function signIn(identifier: string, password: string) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
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
  return <AuthContext.Provider value={{ user, busy, signIn, logout }}>{children}</AuthContext.Provider>;
}
