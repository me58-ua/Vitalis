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

export async function downloadDocument(document: Pick<DocumentItem, 'id' | 'patient_user_id'>, role: 'patient' | 'professional', userId: string, signal: AbortSignal) {
  const path = role === 'patient'
    ? `/patients/me/health/documents/${encodeURIComponent(document.id)}`
    : `/professionals/${encodeURIComponent(userId)}/patients/${encodeURIComponent(document.patient_user_id)}/health/documents/${encodeURIComponent(document.id)}`;
  const { data } = await api.get<Blob>(path, { responseType: 'blob', signal });
  if (signal.aborted) return;
  const url = URL.createObjectURL(data);
  const link = window.document.createElement('a');
  const extension = { 'application/pdf': 'pdf', 'image/png': 'png', 'image/jpeg': 'jpg' }[data.type] ?? 'bin';
  link.href = url;
  link.download = `documento-${document.id}.${extension}`;
  window.document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
