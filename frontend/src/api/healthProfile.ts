import { api } from './client';
import type { components } from '../types/api.generated';

type HealthProfileResponse = components['schemas']['PatientHealthProfileResponse'];
type HealthProfile = Omit<HealthProfileResponse, 'appointment_follow_ups'> & {
  // Older API deployments can omit this section.
  appointment_follow_ups?: HealthProfileResponse['appointment_follow_ups'] | null;
};
export async function getHealthProfile(signal: AbortSignal) {
  return (await api.get<HealthProfile>('/patients/me/health-profile', { signal })).data;
}
