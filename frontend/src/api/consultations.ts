import axios from 'axios';
import { api } from './client';
import { getProfessionalAppointments } from './professional';
import { errorMessage } from './errors';
import type { PatientAppointmentPage, VideoAttendanceRequest, VideoAttendanceResponse } from '../types/api';
import type { AppointmentResponse, AppointmentStatusUpdate, ChatMessagePage, ChatRoom, ProfessionalAppointment, PublicProfessional, VideoJoin } from '../types/api';

export class ConsultationStateError extends Error {}

export async function getPatientAppointments(page: number, signal: AbortSignal) {
  return (await api.get<PatientAppointmentPage>('/patients/me/appointments', { params: { page, page_size: 20 }, signal })).data;
}
export async function recordVideoAttendance(appointmentId: string, event: VideoAttendanceRequest['event'], signal: AbortSignal) {
  return (await api.post<VideoAttendanceResponse>(`/appointments/${encodeURIComponent(appointmentId)}/video/attendance`, { event }, { signal })).data;
}

export async function listVideoAppointments(signal: AbortSignal) {
  const found = new Map<string, ProfessionalAppointment>();
  for (let page = 1; ; page += 1) {
    const response = await getProfessionalAppointments({ upcoming_only: false, status: 'confirmed', page, page_size: 100 }, signal);
    const previous = found.size;
    response.appointments.forEach(item => found.set(item.id, item));
    if (found.size >= response.total) return [...found.values()].filter(item => item.type === 'video');
    if (found.size === previous) throw new Error('No se pudieron recuperar todas las citas.');
  }
}
export async function findVideoAppointment(id: string, date: string | undefined, signal: AbortSignal) {
  let loaded = 0;
  for (let page = 1; ; page += 1) {
    const response = await getProfessionalAppointments({ upcoming_only: false, from_date: date, to_date: date, page, page_size: 100 }, signal);
    const found = response.appointments.find(item => item.id === id);
    if (found) return found;
    loaded += response.appointments.length;
    if (loaded >= response.total || response.appointments.length === 0) return null;
  }
}
export async function updateConsultationStatus(professionalId: string, appointmentId: string, status: 'confirmed' | 'completed', signal: AbortSignal) {
  const payload: AppointmentStatusUpdate = { status };
  return (await api.patch<AppointmentResponse>(`/professionals/${encodeURIComponent(professionalId)}/appointments/${encodeURIComponent(appointmentId)}/status`, payload, { signal })).data;
}
export async function joinVideo(appointmentId: string, signal: AbortSignal) {
  return (await api.post<VideoJoin>(`/appointments/${encodeURIComponent(appointmentId)}/video/join`, undefined, { signal })).data;
}
export async function getChatRoom(appointmentId: string, signal: AbortSignal) {
  return (await api.get<ChatRoom>(`/appointments/${encodeURIComponent(appointmentId)}/chat`, { signal })).data;
}
export async function getChatMessages(appointmentId: string, signal: AbortSignal, cursor?: { before_id?: string; after_id?: string }) {
  return (await api.get<ChatMessagePage>(`/appointments/${encodeURIComponent(appointmentId)}/chat/messages`, { params: { limit: 50, ...cursor }, signal })).data.messages;
}
export async function getPublicProfessional(id: string, signal: AbortSignal) {
  return (await api.get<PublicProfessional>(`/professionals/${encodeURIComponent(id)}`, { signal })).data;
}
export function consultationError(error: unknown): string {
  if (error instanceof ConsultationStateError) return error.message;
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data.detail;
    if (detail === 'Video join window is closed') return 'Todavía no se ha abierto el acceso según el horario de la cita. Puedes entrar desde 10 minutos antes de su inicio.';
    if (detail === 'Video is unavailable for this appointment') return 'Esta cita debe ser de vídeo y estar confirmada para acceder.';
    if (error.response?.status === 403) return 'No tienes acceso a esta consulta o su estado ya no permite esta acción.';
    if (error.response?.status === 404) return 'No se ha encontrado la consulta.';
    if (error.response?.status === 503) return 'El servicio de videoconsulta no está disponible. Inténtalo de nuevo más tarde.';
    if (error.response?.status === 409) return 'La cita ha cambiado. Actualiza sus datos antes de continuar.';
  }
  return errorMessage(error);
}

export function chatSocketUrl(appointmentId: string, accessToken: string): string {
  const base = import.meta.env.VITE_API_BASE_URL;
  if (!base) throw new Error('La conexión con el servidor no está configurada.');
  const url = new URL(base);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error('Dirección de servidor no válida.');
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = `${url.pathname.replace(/\/$/, '')}/ws/chat/${encodeURIComponent(appointmentId)}`;
  url.search = ''; url.hash = '';
  url.searchParams.set('token', accessToken);
  return url.toString();
}
