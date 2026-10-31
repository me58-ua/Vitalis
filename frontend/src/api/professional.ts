import { api } from './client';
import type { ProfessionalDashboard, ProfessionalAppointmentPage, ProfessionalAppointmentQuery, ProfessionalAppointmentCreate,
  ProfessionalPatientPage, ProfessionalProfile, ProfessionalHistoryPage, ProfessionalAppointmentCancel } from '../types/api';

export async function getProfessionalDashboard(signal: AbortSignal) {
  return (await api.get<ProfessionalDashboard>('/professionals/me/dashboard', { signal })).data;
}
export async function getProfessionalAppointments(params: ProfessionalAppointmentQuery, signal: AbortSignal) {
  return (await api.get<ProfessionalAppointmentPage>('/professionals/me/appointments', { params, signal })).data;
}
export async function getProfessionalPatients(search: string, page: number, signal: AbortSignal) {
  return (await api.get<ProfessionalPatientPage>('/professionals/me/patients', { params: { search: search || undefined, page, page_size: 20 }, signal })).data;
}
export async function getProfessionalProfile(signal: AbortSignal) {
  return (await api.get<ProfessionalProfile>('/professionals/me/profile', { signal })).data;
}
export async function createProfessionalAppointment(id: string, payload: ProfessionalAppointmentCreate, signal: AbortSignal) {
  await api.post(`/professionals/${encodeURIComponent(id)}/appointments`, payload, { signal });
}
export async function cancelProfessionalAppointment(id: string, appointmentId: string, cancellationReason: string | null, signal: AbortSignal) {
  const payload: ProfessionalAppointmentCancel = { cancellation_reason: cancellationReason };
  await api.post(`/professionals/${encodeURIComponent(id)}/appointments/${encodeURIComponent(appointmentId)}/cancel`, payload, { signal });
}
export async function getProfessionalHistory(id: string, page: number, signal: AbortSignal) {
  return (await api.get<ProfessionalHistoryPage>(`/professionals/${encodeURIComponent(id)}/appointments/history`, { params: { page, page_size: 20 }, signal })).data;
}
