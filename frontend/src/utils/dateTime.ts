export type DateTimeKind = 'date' | 'time' | 'datetime-local';

export function validDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(`${value}T12:00:00Z`))
    && new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10) === value;
}
export function localizedValue(value: string, kind: DateTimeKind, seconds = false): string {
  if (!value) return '';
  if (kind === 'time') return value.slice(0, seconds ? 8 : 5);
  const [day = '', clock] = value.split('T');
  const parts = day.split('-');
  if (parts.length !== 3) return value;
  const clockText = clock?.slice(0, seconds ? 8 : 5) ?? '';
  return `${parts[2]}/${parts[1]}/${parts[0]}${kind === 'datetime-local' ? ` ${seconds && clockText.length === 5 ? `${clockText}:00` : clockText}` : ''}`;
}
export function canonicalValue(value: string, kind: DateTimeKind, seconds = false): string {
  if (!value.trim()) return '';
  if (kind === 'time') {
    const pattern = seconds ? /^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/ : /^(?:[01]\d|2[0-3]):[0-5]\d$/;
    return pattern.test(value) ? value : '';
  }
  const match = /^(\d{2})\/(\d{2})\/(\d{4})(?: ([0-9:]+))?$/.exec(value);
  if (!match) return '';
  const date = `${match[3]}-${match[2]}-${match[1]}`;
  if (!validDate(date)) return '';
  if (kind === 'date') return match[4] ? '' : date;
  const clock = canonicalValue(match[4] ?? '', 'time', seconds);
  return clock ? `${date}T${clock}` : '';
}

export const dateFormat = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Europe/Madrid' });
export const dateTimeFormat = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'Europe/Madrid' });
export const timeFormat = new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZone: 'Europe/Madrid' });
