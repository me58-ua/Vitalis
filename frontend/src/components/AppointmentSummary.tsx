import type { AppointmentSummary } from '../types/api';

export const appointmentStatuses = { pending: 'Pendiente', confirmed: 'Confirmada', cancelled: 'Anulada', completed: 'Finalizada', no_show: 'No presentado' };
export const appointmentTypes = { video: 'Videoconsulta', in_person: 'Presencial' };
const formatter = new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' });
export function appointmentDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : formatter.format(date);
}
export function AppointmentInfo({ item }: { item: AppointmentSummary }) {
  return <><strong>{item.patient_name}</strong><span>Profesional: {item.professional_name}</span><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time><span>{appointmentTypes[item.type]} · {appointmentStatuses[item.status]}</span></>;
}
