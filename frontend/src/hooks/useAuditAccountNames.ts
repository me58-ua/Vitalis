import { useCallback, useMemo } from 'react';
import axios from 'axios';
import { getAdminUser } from '../api/admin';
import { useAuth } from '../auth/AuthContext';
import { useAdminQuery } from './useAdminQuery';
import type { AuditPage } from '../types/api';

export function auditAccountId(item: AuditPage['items'][number]): string | null {
  return item.entidad === 'user' || item.entidad === 'user_role' ? item.entidad_id : null;
}

interface AccountName { name: string | null; unavailable: boolean }

export function useAuditAccountNames(items: AuditPage['items'] | undefined) {
  const { user } = useAuth();
  const ids = useMemo(() => [...new Set(items?.flatMap(item => {
    const target = auditAccountId(item);
    return [item.actor_id, target, item.patient_id].filter(id => id !== null);
  }) ?? [])], [items]);
  const load = useCallback(async (signal: AbortSignal) => {
    const names: Record<string, AccountName> = {};
    // Bound parallel requests, and resolve each account only once per result page.
    let next = 0;
    await Promise.all(Array.from({ length: Math.min(4, ids.length) }, async () => {
      while (next < ids.length && !signal.aborted) {
        const id = ids[next++];
        if (!id) continue;
        if (id === user?.id) { names[id] = { name: user.name, unavailable: false }; continue; }
        try {
          const account = await getAdminUser(id, signal);
          names[id] = { name: account.name, unavailable: false };
        } catch (error: unknown) {
          if (signal.aborted) return;
          names[id] = { name: null, unavailable: axios.isAxiosError(error) && error.response?.status === 404 };
        }
      }
    }));
    return names;
  }, [ids, user]);
  const state = useAdminQuery(load);
  return { ...state, failed: Object.values(state.data ?? {}).some(item => !item.name && !item.unavailable) };
}
