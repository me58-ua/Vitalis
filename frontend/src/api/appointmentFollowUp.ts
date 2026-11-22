import { api } from './client';
import type { components } from '../types/api.generated';

export type FollowUpNotes = components['schemas']['AppointmentFollowUpNotes'];
export type ProfessionalFollowUp = components['schemas']['ProfessionalAppointmentFollowUp'];
export type PatientFollowUp = components['schemas']['PatientAppointmentFollowUp'];
export type PatientAppointmentHistory = components['schemas']['PatientAppointmentHistory'];
export const appointmentHistoryPath = '/patientPanel/historial';

export function patientAppointmentPath(id: string) {
  return `/patientPanel/misCitas/${encodeURIComponent(id)}`;
}

export function professionalFollowUpPath(id: string) {
  return `/professionalDashboard/citas/${encodeURIComponent(id)}/seguimiento`;
}

export async function getProfessionalFollowUp(id: string, signal: AbortSignal) {
  return (await api.get<ProfessionalFollowUp>(`/professionals/me/appointments/${encodeURIComponent(id)}/follow-up`, { signal })).data;
}

export async function saveFollowUpNotes(id: string, data: FollowUpNotes, signal: AbortSignal) {
  return (await api.put<ProfessionalFollowUp>(`/professionals/me/appointments/${encodeURIComponent(id)}/follow-up`, data, { signal })).data;
}

export async function getPatientFollowUp(id: string, signal: AbortSignal) {
  return (await api.get<PatientFollowUp>(`/patients/me/appointments/${encodeURIComponent(id)}/follow-up`, { signal })).data;
}

export async function getPatientAppointmentHistory(params: URLSearchParams, signal: AbortSignal) {
  return (await api.get<PatientAppointmentHistory>('/patients/me/appointments/history', { params, signal })).data;
}
