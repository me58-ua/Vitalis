import axios from 'axios';
import { api } from './client';
import { errorMessage } from './errors';
import type { ChatAvailability, ProfessionalDirectory, SpontaneousChat, SpontaneousChatPage, SpontaneousMessage, SpontaneousMessagePage } from '../types/api';

export async function listSpontaneousChats(page: number, signal: AbortSignal) {
  return (await api.get<SpontaneousChatPage>('/spontaneous-chats', { params: { page, page_size: 20 }, signal })).data;
}
export async function getSpontaneousChat(id: string, signal: AbortSignal) {
  return (await api.get<SpontaneousChat>(`/spontaneous-chats/${encodeURIComponent(id)}`, { signal })).data;
}
export async function startSpontaneousChat(professionalId: string, signal: AbortSignal) {
  return (await api.post<SpontaneousChat>('/spontaneous-chats', { professional_id: professionalId }, { signal })).data;
}
export async function closeSpontaneousChat(id: string, signal: AbortSignal) {
  return (await api.post<SpontaneousChat>(`/spontaneous-chats/${encodeURIComponent(id)}/close`, undefined, { signal })).data;
}
export async function getSpontaneousMessages(id: string, signal: AbortSignal, cursor?: { before_id?: string; after_id?: string }) {
  return (await api.get<SpontaneousMessagePage>(`/spontaneous-chats/${encodeURIComponent(id)}/messages`, { params: { limit: 50, ...cursor }, signal })).data;
}
export async function sendSpontaneousMessage(id: string, clientId: string, content: string, file: File | null, signal: AbortSignal) {
  const form = new FormData(); form.append('client_id', clientId); form.append('content', content);
  if (file) form.append('file', file);
  return (await api.post<SpontaneousMessage>(`/spontaneous-chats/${encodeURIComponent(id)}/messages`, form, { signal })).data;
}
export async function getSpontaneousFile(chatId: string, messageId: string, signal: AbortSignal) {
  return (await api.get<Blob>(`/spontaneous-chats/${encodeURIComponent(chatId)}/messages/${encodeURIComponent(messageId)}/file`, { signal, responseType: 'blob' })).data;
}
export async function getChatDoctors(search: string, page: number, signal: AbortSignal) {
  const directory = (await api.get<ProfessionalDirectory>('/professionals', { params: { name: search || undefined, page, page_size: 10, is_accepting_new_patients: true }, signal })).data;
  const professionals = await Promise.all(directory.professionals.map(async doctor => ({ ...doctor,
    availability: (await api.get<ChatAvailability>(`/professionals/${encodeURIComponent(doctor.id)}/chat-availability`, { signal })).data })));
  return { ...directory, professionals };
}
export function spontaneousChatError(error: unknown) {
  const messages: Record<string, string> = {
    CHAT_OUTSIDE_AVAILABILITY: 'El médico no está disponible para chat ahora: puede estar fuera de horario, con una cita o en una ausencia. Puedes consultar el historial y volver más tarde.',
    CHAT_CLOSED: 'Esta conversación ya está cerrada. Puedes iniciar otra cuando el médico esté disponible.',
    CHAT_FILE_TOO_LARGE_OR_EMPTY: 'Adjunta un archivo no vacío de hasta 10 MiB.',
    CHAT_FILE_TYPE_INVALID: 'El archivo debe ser un PDF o una imagen JPEG/PNG válida.',
    CHAT_MESSAGE_INVALID: 'Escribe un mensaje de hasta 2000 caracteres o adjunta un archivo.',
    CHAT_REQUEST_CONFLICT: 'Este envío ya se registró con otros datos. Actualiza el historial antes de volver a enviarlo.',
    CHAT_NOT_FOUND: 'La conversación no existe o no pertenece a tu cuenta.',
    CHAT_FILE_NOT_FOUND: 'El adjunto no está disponible.',
  };
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === 'string' && messages[detail]) return messages[detail];
  }
  return errorMessage(error);
}

export const availabilityLabels: Record<ChatAvailability['reason'], string> = {
  available: 'Disponible para chat', outside_hours: 'Fuera del horario de chat', blocked: 'No disponible por ausencia', busy: 'Atendiendo una cita', unavailable: 'No disponible',
};
