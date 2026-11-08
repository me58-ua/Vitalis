import type { ProfessionalAppointment } from '../types/api';

const dateFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Madrid', year: 'numeric', month: '2-digit', day: '2-digit' });
const clockFormatter = new Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

export function madridDay(value: Date | string = new Date()): string {
  const parts = dateFormatter.formatToParts(typeof value === 'string' ? new Date(value) : value);
  const part = (type: string) => parts.find(item => item.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}
export function validCalendarDay(value: string | null): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
export function addDays(day: string, amount: number): string {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}
export function mondayOf(day: string): string {
  return addDays(day, -((new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7));
}
export function dayLabel(day: string, options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long', year: 'numeric' }) {
  return new Intl.DateTimeFormat('es-ES', { ...options, timeZone: 'UTC' }).format(new Date(`${day}T12:00:00Z`));
}
export function clock(value: string): string { return clockFormatter.format(new Date(value)); }
function minutes(value: string): number {
  const parts = clockFormatter.formatToParts(new Date(value));
  return Number(parts.find(item => item.type === 'hour')?.value ?? 0) * 60 + Number(parts.find(item => item.type === 'minute')?.value ?? 0);
}
export function clipInterval(interval: { start_time: string; end_time: string }, day: string) {
  const first = madridDay(interval.start_time), last = madridDay(interval.end_time);
  if (day < first || day > last) return null;
  const start = day === first ? minutes(interval.start_time) : 0;
  let end = day === last ? minutes(interval.end_time) : 1440;
  if (end <= start && first === last) end = Math.min(1440, start + (Date.parse(interval.end_time) - Date.parse(interval.start_time)) / 60000);
  return end > start ? { start, end } : null;
}
export function minuteLabel(value: number): string {
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

export interface AgendaBlock {
  appointment: ProfessionalAppointment;
  start: number;
  end: number;
  column: number;
  columns: number;
}

// Clip overnight appointments to each visible date; cancelled bookings can overlap.
export function blocksForDay(appointments: ProfessionalAppointment[], day: string): AgendaBlock[] {
  const blocks: AgendaBlock[] = [];
  for (const appointment of appointments) {
    const interval = clipInterval(appointment, day);
    if (interval) blocks.push({ appointment, ...interval, column: 0, columns: 1 });
  }
  blocks.sort((a, b) => a.start - b.start || a.end - b.end || a.appointment.id.localeCompare(b.appointment.id));
  let group: AgendaBlock[] = [], ends: number[] = [], groupEnd = -1;
  function finishGroup() { for (const block of group) block.columns = ends.length; }
  for (const block of blocks) {
    if (block.start >= groupEnd) { finishGroup(); group = []; ends = []; }
    let column = ends.findIndex(end => end <= block.start);
    if (column === -1) column = ends.length;
    ends[column] = block.end;
    block.column = column;
    group.push(block); groupEnd = Math.max(groupEnd, block.end);
  }
  finishGroup();
  return blocks;
}
