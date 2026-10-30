import type { Tokens } from '../types/api';

// Tab-scoped storage survives reloads without switching accounts in other tabs.
// Tokens are JavaScript-readable, as required by the existing bearer-token API.
const storageKey = 'vitalis.session';
function storage(): Storage | null {
  try { return typeof window === 'undefined' ? null : window.sessionStorage; }
  catch { return null; }
}
function restore(): Tokens | null {
  try {
    const raw = storage()?.getItem(storageKey);
    const value: unknown = raw ? JSON.parse(raw) : null;
    if (typeof value === 'object' && value !== null && 'access_token' in value && 'refresh_token' in value && 'token_type' in value
      && typeof value.access_token === 'string' && value.access_token && typeof value.refresh_token === 'string' && value.refresh_token
      && value.token_type === 'bearer') return { access_token: value.access_token, refresh_token: value.refresh_token, token_type: value.token_type };
    storage()?.removeItem(storageKey);
  } catch { /* An unavailable browser store leaves the session in memory. */ }
  return null;
}
function persist(value: Tokens | null) {
  try {
    if (value) storage()?.setItem(storageKey, JSON.stringify(value));
    else storage()?.removeItem(storageKey);
  } catch { /* Storage-disabled browsers can still use an in-memory session. */ }
}
let tokens: Tokens | null = restore();
let generation = 0;
const listeners = new Set<() => void>();

export const session = {
  read: () => tokens,
  generation: () => generation,
  rotate(value: Tokens) {
    tokens = value;
    persist(value);
  },
  replace(value: Tokens | null) {
    tokens = value;
    persist(value);
    generation += 1;
    listeners.forEach((listener) => listener());
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  },
};
