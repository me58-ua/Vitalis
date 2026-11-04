import { api } from './client';
import type { Notification, NotificationPage, UnreadCount } from '../types/api';

export async function getUnreadCount(signal: AbortSignal) {
  const { data } = await api.get<UnreadCount>('/notifications/unread-count', { signal });
  return data.count;
}
export async function getNotifications(signal: AbortSignal) {
  const { data } = await api.get<NotificationPage>('/notifications', { params: { limit: 50 }, signal });
  return data;
}
export async function markRead(id: string, signal: AbortSignal) {
  const { data } = await api.patch<Notification>(`/notifications/${encodeURIComponent(id)}/read`, undefined, { signal });
  return data;
}
