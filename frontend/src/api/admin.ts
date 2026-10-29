import { api } from './client';
import type { AdminUserPage, AuditPage, AuditQuery } from '../types/api';

export async function getAdminTotals(signal: AbortSignal) {
  const count = async (role?: 'patient' | 'professional') => {
    const { data } = await api.get<AdminUserPage>('/admin/users', { params: { role, page: 1, page_size: 1 }, signal });
    return data.total;
  };
  const [total, patients, professionals] = await Promise.all([count(), count('patient'), count('professional')]);
  return { total, patients, professionals };
}

export async function getAudits(params: AuditQuery, signal: AbortSignal) {
  const { data } = await api.get<AuditPage>('/admin/audit-logs', { params, signal });
  return data;
}
