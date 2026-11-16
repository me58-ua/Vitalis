import { api } from './client';
import type { components } from '../types/api.generated';

export type HealthProfile = components['schemas']['PatientHealthProfileResponse'];
export async function getHealthProfile(signal: AbortSignal) {
  return (await api.get<HealthProfile>('/patients/me/health-profile', { signal })).data;
}
