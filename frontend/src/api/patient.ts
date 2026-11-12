import { api } from './client';
import axios from 'axios';
import { errorMessage } from './errors';
import type { PatientAppointmentPage, PatientProfile, PatientRiskSummary, PatientRiskHistory, PatientHabitPage, PatientDocument } from '../types/api';
import type { DocumentType } from './documents';

export function patientUploadError(error: unknown): string {
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data.detail;
    if (detail === 'Health document must be a PDF, JPEG, or PNG file') return 'El archivo debe ser PDF, JPEG o PNG.';
    if (detail === 'File exceeds the maximum allowed size') return 'El archivo supera el tamaño permitido por el servidor. Selecciona uno más pequeño.';
    if (detail === 'Patient profile not found') return 'No se ha encontrado tu perfil de paciente. No se pudo subir el documento.';
  }
  return errorMessage(error);
}

export async function getPatientProfile(signal: AbortSignal) {
  return (await api.get<PatientProfile>('/patients/me/profile', { signal })).data;
}
export async function getPatientRisks(profileId: string, signal: AbortSignal) {
  return (await api.get<PatientRiskSummary>(`/patients/${encodeURIComponent(profileId)}/risk-summary`, { signal })).data;
}
export async function getPatientRiskHistory(profileId: string, model: string, cursor: string | null, signal: AbortSignal) {
  return (await api.get<PatientRiskHistory>(`/patients/${encodeURIComponent(profileId)}/risk-history`, {
    params: { model: model || undefined, cursor: cursor || undefined, limit: 20 }, signal,
  })).data;
}
export async function getPatientHabits(page: number, signal: AbortSignal) {
  return (await api.get<PatientHabitPage>('/patients/me/health/habits', { params: { page, page_size: 20 }, signal })).data;
}
export async function setPatientAIConsent(enabled: boolean, signal: AbortSignal) {
  return (await api.patch<PatientProfile>('/patients/me/ai-consent', { ai_processing_consent: enabled }, { signal })).data;
}
export async function uploadPatientDocument(file: File, tipo: DocumentType, descripcion: string, signal: AbortSignal) {
  const body = new FormData();
  body.append('file', file); body.append('tipo', tipo);
  if (descripcion.trim()) body.append('descripcion', descripcion.trim());
  return (await api.post<PatientDocument>('/patients/me/health/documents', body, { signal })).data;
}

// This endpoint sorts descending and exposes no upcoming filter. Inspect every
// page so a more distant appointment never replaces the nearest appointment.
export async function getDashboardAppointments(signal: AbortSignal) {
  const rows = new Map<string, PatientAppointmentPage['appointments'][number]>();
  for (let page = 1; ; page += 1) {
    const data = (await api.get<PatientAppointmentPage>('/patients/me/appointments', { params: { page, page_size: 100 }, signal })).data;
    const previous = rows.size;
    data.appointments.forEach(item => rows.set(item.id, item));
    if (rows.size >= data.total) return [...rows.values()];
    if (rows.size === previous) throw new Error('No se pudieron recuperar todas las citas.');
  }
}
