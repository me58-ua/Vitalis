import { api, publicApi } from './client';
import type { Registration, Tokens, User } from '../types/api';

export async function login(identifier: string, password: string) {
  const form = new URLSearchParams({ username: identifier, password });
  const { data } = await publicApi.post<Tokens>('/auth/login', form);
  return data;
}
export async function register(payload: Registration) {
  const { data } = await publicApi.post<User>('/auth/register', payload);
  return data;
}
export async function currentUser(signal?: AbortSignal) {
  const { data } = await api.get<User>('/auth/me', { signal });
  return data;
}

export async function endSession() {
  await api.post('/auth/logout');
}

export async function requestPasswordReset(email: string) {
  await publicApi.post('/auth/forgot-password', { email });
}

export async function resetPassword(token: string, password: string) {
  await publicApi.post('/auth/reset-password', { token, password });
}
