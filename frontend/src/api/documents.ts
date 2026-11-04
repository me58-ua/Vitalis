import { api } from './client';
import type { components } from '../types/api.generated';

export type DocumentSearch = components['schemas']['HealthDocumentSearchResponse'];
export type DocumentItem = components['schemas']['HealthDocumentSearchItem'];
export type DocumentType = components['schemas']['HealthDocumentType'];

export async function searchDocuments(q: string, tipo: DocumentType | '', page: number, signal: AbortSignal) {
  const { data } = await api.get<DocumentSearch>('/health/documents/search', {
    params: { q, tipo: tipo || undefined, page, page_size: 10 }, signal,
  });
  return data;
}

export async function downloadDocument(document: DocumentItem, role: 'patient' | 'professional', userId: string, signal: AbortSignal) {
  const path = role === 'patient'
    ? `/patients/me/health/documents/${encodeURIComponent(document.id)}`
    : `/professionals/${encodeURIComponent(userId)}/patients/${encodeURIComponent(document.patient_user_id)}/health/documents/${encodeURIComponent(document.id)}`;
  const { data } = await api.get<Blob>(path, { responseType: 'blob', signal });
  return data;
}
