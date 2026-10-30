import { api } from './client';
import type { AdminUserPage, AuditPage, AuditQuery, AppointmentList, UpcomingAppointments, AppointmentQuery, CreateAppointment, UpdateAppointment, AdminMonthlyMetrics } from '../types/api';

export async function getAdminMonthlyMetrics(signal: AbortSignal) {
  return (await api.get<AdminMonthlyMetrics>('/admin/metrics/monthly', { signal })).data;
}

export async function getAudits(params: AuditQuery, signal: AbortSignal) {
  const { data } = await api.get<AuditPage>('/admin/audit-logs', { params, signal });
  return data;
}

export async function getAdminAppointments(params: AppointmentQuery, signal: AbortSignal) {
  return (await api.get<AppointmentList>('/admin/appointments', { params, signal })).data;
}
export async function getUpcomingAppointments(signal: AbortSignal) {
  return (await api.get<UpcomingAppointments>('/admin/appointments/upcoming-month', { signal })).data;
}
export async function createAdminAppointment(payload: CreateAppointment, signal: AbortSignal) {
  await api.post('/admin/appointments', payload, { signal });
}
export async function cancelAdminAppointment(id: string, reason: string | null, signal: AbortSignal) {
  const payload: UpdateAppointment = { status: 'cancelled', reason };
  await api.patch(`/admin/appointments/${id}`, payload, { signal });
}
export async function getAppointmentUsers(role: 'patient' | 'professional', search: string, page: number, signal: AbortSignal) {
  return (await api.get<AdminUserPage>('/admin/users', { params: { role, search: search || undefined, page, page_size: 20 }, signal })).data;
}
