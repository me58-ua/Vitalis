import type { WorkingHours } from '../types/api';

export const workingDays = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
export interface WorkingHoursGroup { key: string; rows: WorkingHours[]; row: WorkingHours; label: string }

export function groupWorkingHours(rows: WorkingHours[]): WorkingHoursGroup[] {
  const groups = new Map<string, WorkingHours[]>();
  for (const row of rows) {
    const key = [row.channel, row.start_time.slice(0, 5), row.end_time.slice(0, 5), row.channel === 'chat' ? '' : row.slot_duration_min, row.is_active].join('|');
    groups.set(key, [...groups.get(key) ?? [], row]);
  }
  return [...groups.entries()].map(([key, members]) => {
    const sorted = [...members].sort((a, b) => a.day_of_week - b.day_of_week || a.id.localeCompare(b.id));
    const row = sorted[0];
    if (!row) throw new Error('Grupo de horarios vacío.');
    return { key, rows: sorted, row, label: new Intl.ListFormat('es-ES', { type: 'conjunction' }).format(sorted.map(row => workingDays[row.day_of_week] ?? '')) };
  }).sort((a, b) => a.row.day_of_week - b.row.day_of_week || a.row.start_time.localeCompare(b.row.start_time));
}
