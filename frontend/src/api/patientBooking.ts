import axios from 'axios';
import { api, publicApi } from './client';
import { errorMessage } from './errors';
import type { components, paths } from '../types/api.generated';

type Schemas = components['schemas'];
export type BookingProfessional = Schemas['ProfessionalPublicResponse'];
export type DirectoryQuery = NonNullable<paths['/professionals']['get']['parameters']['query']>;
type AvailabilityQuery = paths['/professionals/{professional_id}/availability']['get']['parameters']['query'];
export type BookingSlot = Schemas['AvailabilitySlot'];

export async function getBookingProfessionals(params: DirectoryQuery, signal: AbortSignal) {
  return (await publicApi.get<Schemas['ProfessionalListResponse']>('/professionals', { params, signal })).data;
}

export async function getBookingProfessional(id: string, signal: AbortSignal) {
  return (await publicApi.get<BookingProfessional>(`/professionals/${encodeURIComponent(id)}`, { signal })).data;
}

export async function getBookingAvailability(id: string, params: AvailabilityQuery, signal: AbortSignal) {
  return (await api.get<Schemas['AvailabilityResponse']>(`/professionals/${encodeURIComponent(id)}/availability`, { params, signal })).data;
}

export async function bookPatientAppointment(data: Schemas['PatientAppointmentCreate']) {
  return (await api.post<Schemas['AdminAppointmentResponse']>('/patients/me/appointments', data)).data;
}

export function bookingError(error: unknown) {
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail;
    if (detail === 'OUTSIDE_WORKING_HOURS') return 'El horario seleccionado está fuera de la jornada del profesional. Elige otro horario.';
    if (error.response?.status === 409 || detail === 'Selected time is not an available slot') {
      return 'El horario seleccionado ya no está disponible. Elige otro horario.';
    }
    if (detail === 'Professional is not accepting new patients') return 'El profesional ya no acepta nuevos pacientes.';
    if (detail === 'Teleconsultation is not enabled') return 'El profesional no ofrece videoconsultas.';
  }
  return errorMessage(error);
}
