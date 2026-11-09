import { api } from './client';
import type { WorkingHours, WorkingHoursCreate, WorkingHoursUpdate } from '../types/api';
import type { WorkingHoursBatch } from '../types/api';

export async function saveWorkingHoursBatch(payload: WorkingHoursBatch, signal: AbortSignal) {
  return (await api.post<WorkingHours[]>('/professionals/me/working-hours/batch', payload, { signal })).data;
}
export async function deleteWorkingHoursBatch(ids: string[], signal: AbortSignal) {
  await api.post('/professionals/me/working-hours/batch-delete', { schedule_ids: ids }, { signal });
}

export async function getWorkingHours(signal: AbortSignal) {
  return (await api.get<WorkingHours[]>('/professionals/me/working-hours', { signal })).data;
}
export async function saveWorkingHours(payload: WorkingHoursCreate | WorkingHoursUpdate, id: string | null, signal: AbortSignal) {
  return id ? (await api.patch<WorkingHours>(`/professionals/me/working-hours/${encodeURIComponent(id)}`, payload, { signal })).data
    : (await api.post<WorkingHours>('/professionals/me/working-hours', payload, { signal })).data;
}
export async function deleteWorkingHours(id: string, signal: AbortSignal) {
  await api.delete(`/professionals/me/working-hours/${encodeURIComponent(id)}`, { signal });
}
import type { ProfessionalProfileUpdate, ProfessionalTimeBlock, ProfessionalTimeBlockCreate } from '../types/api';

export async function updateProfessionalProfile(payload: ProfessionalProfileUpdate, signal: AbortSignal) {
  return (await api.patch<ProfessionalProfile>('/professionals/me/profile', payload, { signal })).data;
}
export async function getTimeBlocks(from: string, to: string, signal: AbortSignal) {
  return (await api.get<ProfessionalTimeBlock[]>('/professionals/me/time-blocks', { params: { from_date: from, to_date: to }, signal })).data;
}
export async function createTimeBlock(payload: ProfessionalTimeBlockCreate, signal: AbortSignal) {
  return (await api.post<ProfessionalTimeBlock>('/professionals/me/time-blocks', payload, { signal })).data;
}
export async function deleteTimeBlock(id: string, signal: AbortSignal) {
  await api.delete(`/professionals/me/time-blocks/${encodeURIComponent(id)}`, { signal });
}
import type { PatientHealthSnapshot, ProfessionalPrescriptionPage, Prescription, ProfessionalAppointment } from '../types/api';

export async function getProfessionalWeek(fromDate: string, toDate: string, signal: AbortSignal) {
  const appointments = new Map<string, ProfessionalAppointment>();
  for (let page = 1; ; page += 1) {
    const result = await getProfessionalAppointments({ from_date: fromDate, to_date: toDate, upcoming_only: false, page, page_size: 100 }, signal);
    const before = appointments.size;
    for (const item of result.appointments) {
      if (!Number.isFinite(Date.parse(item.start_time)) || !Number.isFinite(Date.parse(item.end_time)) || Date.parse(item.end_time) <= Date.parse(item.start_time)) {
        throw new Error('Las fechas de una cita no son válidas.');
      }
      appointments.set(item.id, item);
    }
    if (appointments.size >= result.total) return [...appointments.values()];
    if (appointments.size === before) throw new Error('No se pudo cargar la semana completa.');
  }
}

export async function getPatientSnapshot(patientId: string, signal: AbortSignal) {
  return (await api.get<PatientHealthSnapshot>(`/professionals/patients/${encodeURIComponent(patientId)}/health-snapshot`, { signal })).data;
}
export async function getPatientHistory(professionalId: string, patientId: string, page: number, signal: AbortSignal) {
  return (await api.get<ProfessionalHistoryPage>(`/professionals/${encodeURIComponent(professionalId)}/appointments/history`, { params: { patient_id: patientId, page, page_size: 10 }, signal })).data;
}
export async function getPatientPrescriptions(professionalId: string, patientId: string, page: number, signal: AbortSignal) {
  return (await api.get<ProfessionalPrescriptionPage>(`/professionals/${encodeURIComponent(professionalId)}/prescriptions`, { params: { patient_id: patientId, page, page_size: 10 }, signal })).data;
}
export async function attachPrescription(professionalId: string, appointmentId: string, file: File, notes: string, signal: AbortSignal) {
  const form = new FormData();
  form.append('file', file);
  if (notes.trim()) form.append('notas', notes.trim());
  return (await api.post<Prescription>(`/professionals/${encodeURIComponent(professionalId)}/appointments/${encodeURIComponent(appointmentId)}/prescription`, form, { signal })).data;
}

export async function getAppointmentPrescription(professionalId: string, patientId: string, appointmentId: string, signal: AbortSignal) {
  for (let page = 1, loaded = 0; ; page += 1) {
    const result = await getPatientPrescriptions(professionalId, patientId, page, signal);
    const found = result.prescriptions.find(item => item.appointment_id === appointmentId);
    if (found) return found;
    loaded += result.prescriptions.length;
    if (loaded >= result.total) return null;
    if (result.prescriptions.length === 0) throw new Error('No se pudieron recuperar todas las recetas.');
  }
}

export async function downloadProfessionalPrescription(professionalId: string, appointmentId: string, signal: AbortSignal) {
  return (await api.get<Blob>(`/professionals/${encodeURIComponent(professionalId)}/appointments/${encodeURIComponent(appointmentId)}/prescription`, { responseType: 'blob', signal })).data;
}
import type { ProfessionalDashboard, ProfessionalAppointmentPage, ProfessionalAppointmentQuery, ProfessionalAppointmentCreate,
  ProfessionalPatientPage, ProfessionalProfile, ProfessionalHistoryPage, ProfessionalAppointmentCancel } from '../types/api';

export async function getProfessionalDashboard(signal: AbortSignal) {
  return (await api.get<ProfessionalDashboard>('/professionals/me/dashboard', { signal })).data;
}
export async function getProfessionalAppointments(params: ProfessionalAppointmentQuery, signal: AbortSignal) {
  return (await api.get<ProfessionalAppointmentPage>('/professionals/me/appointments', { params, signal })).data;
}
export async function getProfessionalPatients(search: string, page: number, signal: AbortSignal, pageSize = 20) {
  return (await api.get<ProfessionalPatientPage>('/professionals/me/patients', { params: { search: search || undefined, page, page_size: pageSize }, signal })).data;
}
export async function getProfessionalProfile(signal: AbortSignal) {
  return (await api.get<ProfessionalProfile>('/professionals/me/profile', { signal })).data;
}
export async function createProfessionalAppointment(id: string, payload: ProfessionalAppointmentCreate, signal: AbortSignal) {
  await api.post(`/professionals/${encodeURIComponent(id)}/appointments`, payload, { signal });
}
export async function cancelProfessionalAppointment(id: string, appointmentId: string, cancellationReason: string | null, signal: AbortSignal) {
  const payload: ProfessionalAppointmentCancel = { cancellation_reason: cancellationReason };
  await api.post(`/professionals/${encodeURIComponent(id)}/appointments/${encodeURIComponent(appointmentId)}/cancel`, payload, { signal });
}
export async function getProfessionalHistory(id: string, page: number, signal: AbortSignal) {
  return (await api.get<ProfessionalHistoryPage>(`/professionals/${encodeURIComponent(id)}/appointments/history`, { params: { page, page_size: 20 }, signal })).data;
}
