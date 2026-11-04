import type { CSSProperties } from 'react';
import type { ProfessionalAppointment } from '../types/api';
import { appointmentStatuses } from './AppointmentSummary';
import { blocksForDay, clock, dayLabel, madridDay, minuteLabel } from '../utils/agenda';

export function ProfessionalWeekCalendar({ days, selectedDay, appointments, selectedId, onSelect }: {
  days: string[]; selectedDay: string; appointments: ProfessionalAppointment[]; selectedId: string | null;
  onSelect: (item: ProfessionalAppointment, button: HTMLButtonElement) => void;
}) {
  const columns = days.map(day => ({ day, blocks: blocksForDay(appointments, day) }));
  const blocks = columns.flatMap(column => column.blocks);
  const start = Math.floor(Math.min(9 * 60, ...blocks.map(block => block.start)) / 30) * 30;
  const end = Math.ceil(Math.max(18 * 60, ...blocks.map(block => block.end)) / 30) * 30;
  const ticks = Array.from({ length: (end - start) / 30 }, (_, index) => start + index * 30);
  const style: CSSProperties & { '--agenda-days': number; '--agenda-height': string } = { '--agenda-days': days.length, '--agenda-height': `${(end - start) * 2}px` };
  return <div className="agenda-calendar-scroll" tabIndex={0} aria-label="Calendario de citas, desplazamiento vertical">
    <div className="agenda-calendar" style={style}>
      <div className="agenda-day-head agenda-time-heading">Hora</div>
      {columns.map(({ day }) => <h3 key={day} className={`agenda-day-head${day === madridDay() ? ' is-today' : ''}`} data-mobile-visible={day === selectedDay}>
        <span>{dayLabel(day, { weekday: 'short' })}</span><time dateTime={day}>{dayLabel(day, { day: 'numeric', month: 'short' })}</time>
      </h3>)}
      <div className="agenda-time-axis" aria-hidden="true">{ticks.map(tick => <span key={tick} style={{ top: (tick - start) * 2 }}>{minuteLabel(tick)}</span>)}</div>
      {columns.map(({ day, blocks: daily }) => <section key={day} className="agenda-day-column" data-mobile-visible={day === selectedDay} aria-label={dayLabel(day, { weekday: 'long', day: 'numeric', month: 'long' })}>
        {daily.length === 0 && <span className="professional-sr-only">Sin citas</span>}
        {daily.map(block => <button key={block.appointment.id} type="button" className={`agenda-event agenda-event-${block.appointment.status}${block.appointment.id === selectedId ? ' is-selected' : ''}`}
          style={{ top: (block.start - start) * 2, height: Math.max(30, (block.end - block.start) * 2 - 3), left: `calc(${block.column / block.columns * 100}% + 3px)`, width: `calc(${100 / block.columns}% - 6px)` }}
          aria-label={`${block.appointment.patient_name}, ${dayLabel(day)}, ${clock(block.appointment.start_time)} a ${clock(block.appointment.end_time)}, ${appointmentStatuses[block.appointment.status]}`}
          aria-pressed={block.appointment.id === selectedId} aria-controls="agenda-appointment-detail"
          onClick={event => onSelect(block.appointment, event.currentTarget)}>
          <span className="agenda-event-time">{clock(block.appointment.start_time)}–{clock(block.appointment.end_time)}</span>
          <strong>{block.appointment.patient_name}</strong><span className="agenda-event-status">{appointmentStatuses[block.appointment.status]}</span>
        </button>)}
      </section>)}
    </div>
  </div>;
}
