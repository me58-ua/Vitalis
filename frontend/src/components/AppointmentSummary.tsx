import type { AppointmentSummary } from '../types/api';
import { dateTimeFormat as formatter } from '../utils/dateTime';

export const appointmentStatuses = { confirmed: 'Confirmada', cancelled: 'Anulada', completed: 'Finalizada', no_show: 'No presentado' };
export const appointmentTypes = { video: 'Videoconsulta', in_person: 'Presencial' };
export function appointmentDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : formatter.format(date);
}
export function AppointmentInfo({ item }: { item: AppointmentSummary }) {
  return <><strong>{item.patient_name}</strong><span>Profesional: {item.professional_name}</span><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time><span>{appointmentTypes[item.type]} · {appointmentStatuses[item.status]}</span></>;
}
