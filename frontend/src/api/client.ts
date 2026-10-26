import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { session } from './session';
import type { Tokens } from '../types/api';

const baseURL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');
export const apiConfigured = Boolean(baseURL);
export const publicApi = axios.create({ baseURL, timeout: 15000 });
export const api = axios.create({ baseURL, timeout: 15000 });

function requireConfiguration(config: InternalAxiosRequestConfig) {
  if (!apiConfigured) throw new Error('VITE_API_BASE_URL no está configurada.');
  return config;
}
publicApi.interceptors.request.use(requireConfiguration);

interface SessionRequest extends InternalAxiosRequestConfig {
  sessionGeneration?: number;
  retried?: boolean;
}

api.interceptors.request.use((config: SessionRequest) => {
  requireConfiguration(config);
  const current = session.read();
  if (!current) throw new Error('No hay una sesión activa.');
  config.headers.set('Authorization', `Bearer ${current.access_token}`);
  config.sessionGeneration = session.generation();
  return config;
});

let refreshFlight: { generation: number; promise: Promise<Tokens> } | null = null;

async function refreshTokens(): Promise<Tokens> {
  const current = session.read();
  const generation = session.generation();
  if (!current) throw new Error('No hay una sesión activa.');
  if (refreshFlight?.generation === generation) return refreshFlight.promise;
  const promise = publicApi.post<Tokens>('/auth/refresh', { refresh_token: current.refresh_token })
    .then(({ data }) => {
      if (generation !== session.generation()) throw new Error('La sesión ha cambiado.');
      session.rotate(data);
      return data;
    })
    .catch((error: unknown) => {
      if (generation === session.generation()) session.replace(null);
      throw error;
    })
    .finally(() => { if (refreshFlight?.promise === promise) refreshFlight = null; });
  refreshFlight = { generation, promise };
  return promise;
}

api.interceptors.response.use(
  (response) => {
    const config: SessionRequest = response.config;
    if (config.sessionGeneration !== session.generation()) throw new Error('La sesión ha cambiado.');
    return response;
  },
  async (error: unknown) => {
    if (!(error instanceof AxiosError) || !error.config) throw error;
    const config: SessionRequest = error.config;
    if (error.response?.status !== 401 || !session.read()) throw error;
    if (config.sessionGeneration !== session.generation()) {
      // A parallel request may already have refreshed this same access token.
      // Do not retry requests from a different account or a logged-out session.
      throw error;
    }
    if (config.retried) { session.replace(null); throw error; }
    config.retried = true;
    if (config.headers.get('Authorization') === `Bearer ${session.read()?.access_token}`) await refreshTokens();
    return api.request(config);
  },
);
