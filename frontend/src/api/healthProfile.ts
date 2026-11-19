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

export async function updateHealthSharingConsent(enabled: boolean, signal: AbortSignal) {
  await api.patch('/patients/me/consentimiento', { share_health_data: enabled }, { signal });
}

export async function getProfessionalHealthSharing(signal: AbortSignal) {
  return (await api.get<components['schemas']['ProfessionalHealthSharing'][]>('/patients/me/health-profile/sharing', { signal })).data;
}

export async function revokeProfessionalHealthSharing(professionalId: string, signal: AbortSignal) {
  await api.delete(`/patients/me/health-profile/sharing/${encodeURIComponent(professionalId)}`, { signal });
}
