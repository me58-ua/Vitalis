import { createContext, useContext } from 'react';
import type { User } from '../types/api';

export interface AuthState {
  user: User | null;
  busy: boolean;
  logoutError: string;
  signIn: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}
export const AuthContext = createContext<AuthState | null>(null);
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider no está disponible.');
  return value;
}
