import { api } from './client';
import type { ProfessionalProfile, ProfileChangeDecision } from '../types/api';

export async function getPendingProfileChanges(signal: AbortSignal) {
  return (await api.get<ProfessionalProfile[]>('/admin/professionals/profile-changes', { signal })).data;
}
export async function decideProfileChange(id: string, approve: boolean, payload: ProfileChangeDecision, signal: AbortSignal) {
  return (await api.post<ProfessionalProfile>(`/admin/professionals/${encodeURIComponent(id)}/profile-change/${approve ? 'approve' : 'reject'}`, payload, { signal })).data;
}
import type { AdminUserDetail, AdminUserQuery, CreateAdminUser, UpdateAdminUser } from '../types/api';
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
export async function cancelAdminAppointment(id: string, cancellationReason: string | null, signal: AbortSignal) {
  const payload: UpdateAppointment = { status: 'cancelled', cancellation_reason: cancellationReason };
  await api.patch(`/admin/appointments/${id}`, payload, { signal });
}
export async function getAppointmentUsers(role: 'patient' | 'professional', search: string, page: number, signal: AbortSignal) {
  return (await api.get<AdminUserPage>('/admin/users', { params: { role, search: search || undefined, page, page_size: 20 }, signal })).data;
}

export async function getAdminUsers(params: AdminUserQuery, signal: AbortSignal) {
  return (await api.get<AdminUserPage>('/admin/users', { params, signal })).data;
}
export async function getAdminUser(id: string, signal: AbortSignal) {
  return (await api.get<AdminUserDetail>(`/admin/users/${encodeURIComponent(id)}`, { signal })).data;
}
export async function createAdminUser(payload: CreateAdminUser, signal: AbortSignal) {
  return (await api.post<AdminUserDetail>('/admin/users', payload, { signal })).data;
}
export async function updateAdminUser(id: string, payload: UpdateAdminUser, signal: AbortSignal) {
  return (await api.patch<AdminUserDetail>(`/admin/users/${encodeURIComponent(id)}`, payload, { signal })).data;
}
export async function deleteAdminUser(id: string, signal: AbortSignal) {
  await api.delete(`/admin/users/${encodeURIComponent(id)}`, { signal });
}
export async function approveAdminProfessional(id: string, signal: AbortSignal) {
  await api.post(`/admin/professionals/${encodeURIComponent(id)}/approve`, undefined, { signal });
}
