import { api } from './client';
import type { PatientHealthSnapshot, ProfessionalPrescriptionPage, Prescription } from '../types/api';

export async function getPatientSnapshot(patientId: string, signal: AbortSignal) {
  return (await api.get<PatientHealthSnapshot>(`/professionals/patients/${encodeURIComponent(patientId)}/health-snapshot`, { signal })).data;
}
export async function getPatientHistory(professionalId: string, patientId: string, page: number, signal: AbortSignal) {
  return (await api.get<ProfessionalHistoryPage>(`/professionals/${encodeURIComponent(professionalId)}/appointments/history`, { params: { patient_id: patientId, page, page_size: 10 }, signal })).data;
}
export async function getPatientPrescriptions(professionalId: string, patientId: string, page: number, signal: AbortSignal) {
  return (await api.get<ProfessionalPrescriptionPage>(`/professionals/${encodeURIComponent(professionalId)}/prescriptions`, { params: { patient_id: patientId, page, page_size: 10 }, signal })).data;
}
export async function attachPrescription(professionalId: string, appointmentId: string, file: File, notes: string, signal: AbortSignal) {
  const form = new FormData();
  form.append('file', file);
  if (notes.trim()) form.append('notas', notes.trim());
  return (await api.post<Prescription>(`/professionals/${encodeURIComponent(professionalId)}/appointments/${encodeURIComponent(appointmentId)}/prescription`, form, { signal })).data;
}
import type { ProfessionalDashboard, ProfessionalAppointmentPage, ProfessionalAppointmentQuery, ProfessionalAppointmentCreate,
  ProfessionalPatientPage, ProfessionalProfile, ProfessionalHistoryPage, ProfessionalAppointmentCancel } from '../types/api';

export async function getProfessionalDashboard(signal: AbortSignal) {
  return (await api.get<ProfessionalDashboard>('/professionals/me/dashboard', { signal })).data;
}
export async function getProfessionalAppointments(params: ProfessionalAppointmentQuery, signal: AbortSignal) {
  return (await api.get<ProfessionalAppointmentPage>('/professionals/me/appointments', { params, signal })).data;
}
export async function getProfessionalPatients(search: string, page: number, signal: AbortSignal, pageSize = 20) {
  return (await api.get<ProfessionalPatientPage>('/professionals/me/patients', { params: { search: search || undefined, page, page_size: pageSize }, signal })).data;
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
