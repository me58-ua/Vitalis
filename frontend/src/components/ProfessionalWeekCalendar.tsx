import type { CSSProperties } from 'react';
import type { ProfessionalAppointment, ProfessionalTimeBlock, WorkingHours } from '../types/api';
import { appointmentStatuses, appointmentTypes } from './AppointmentSummary';
import { blocksForDay, clipInterval, clock, dayLabel, madridDay, minuteLabel } from '../utils/agenda';
import { workingHourChannels } from '../utils/workingHours';

function localMinutes(value: string) {
  return Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
}

export function ProfessionalWeekCalendar({ days, selectedDay, appointments, timeBlocks = [], workingHours, selectedId, onSelect }: {
  days: string[]; selectedDay: string; appointments: ProfessionalAppointment[]; selectedId: string | null;
  timeBlocks?: ProfessionalTimeBlock[];
  workingHours: WorkingHours[];
  onSelect: (item: ProfessionalAppointment, button: HTMLButtonElement) => void;
}) {
  const columns = days.map(day => {
    const weekday = (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
    return {
      day,
      blocks: blocksForDay(appointments, day),
      unavailable: timeBlocks.flatMap(block => {
        const interval = clipInterval(block, day);
        return interval ? [{ ...interval, block }] : [];
      }),
      hours: workingHours.filter(row => row.is_active && row.day_of_week === weekday)
        .map(row => ({ row, start: localMinutes(row.start_time), end: localMinutes(row.end_time) })),
    };
  });
  const blocks = columns.flatMap(column => [...column.blocks, ...column.unavailable, ...column.hours]);
  const start = Math.floor(Math.min(9 * 60, ...blocks.map(block => block.start)) / 30) * 30;
  const end = Math.ceil(Math.max(18 * 60, ...blocks.map(block => block.end)) / 30) * 30;
  const ticks = Array.from({ length: (end - start) / 30 }, (_, index) => start + index * 30);
  const style: CSSProperties & { '--agenda-days': number; '--agenda-height': string } = { '--agenda-days': days.length, '--agenda-height': `${(end - start) * 2}px` };
  return <>
    <ul className="agenda-channel-legend" aria-label="Franjas semanales por modalidad">{workingHourChannels.map(({ value, label }) =>
      <li key={value} className={`agenda-channel-${value}`}><span className="agenda-channel-dot" aria-hidden="true" />{label}</li>
    )}</ul>
    <div className="agenda-calendar-scroll" tabIndex={0} aria-label="Calendario de citas, desplazamiento vertical">
    <div className="agenda-calendar" style={style}>
      <div className="agenda-day-head agenda-time-heading">Hora</div>
      {columns.map(({ day }) => <h3 key={day} className={`agenda-day-head${day === madridDay() ? ' is-today' : ''}`} data-mobile-visible={day === selectedDay}>
        <span>{dayLabel(day, { weekday: 'short' })}</span><time dateTime={day}>{dayLabel(day, { day: 'numeric', month: 'short' })}</time>
      </h3>)}
      <div className="agenda-time-axis" aria-hidden="true">{ticks.map(tick => <span key={tick} style={{ top: (tick - start) * 2 }}>{minuteLabel(tick)}</span>)}</div>
      {columns.map(({ day, blocks: daily, unavailable, hours }) => <section key={day} className="agenda-day-column" data-mobile-visible={day === selectedDay} aria-label={dayLabel(day, { weekday: 'long', day: 'numeric', month: 'long' })}>
        {hours.map(({ row, start: hourStart, end: hourEnd }) => {
          const lane = workingHourChannels.findIndex(channel => channel.value === row.channel);
          const label = `${workingHourChannels[lane]?.label}: ${minuteLabel(hourStart)}–${minuteLabel(hourEnd)}`;
          return <div key={row.id} className={`agenda-working-band agenda-channel-${row.channel}`} title={label}
            style={{ insetInlineStart: lane * 6 + 1, top: (hourStart - start) * 2, height: (hourEnd - hourStart) * 2 }}>
            <span className="professional-sr-only">{label}</span>
          </div>;
        })}
        {unavailable.map(({ block, start: blockStart, end: blockEnd }) => <div key={block.id} className="agenda-unavailable" style={{ top: (blockStart - start) * 2, height: Math.max(24, (blockEnd - blockStart) * 2 - 3) }}><strong>No disponible</strong><span>{minuteLabel(blockStart)}–{minuteLabel(blockEnd)}</span><span>{block.reason || 'Horario bloqueado'}</span></div>)}
        {daily.length === 0 && <span className="professional-sr-only">Sin citas</span>}
        {daily.map(block => <button key={block.appointment.id} type="button" className={`agenda-event agenda-event-${block.appointment.status} agenda-channel-${block.appointment.type}${block.appointment.id === selectedId ? ' is-selected' : ''}`}
          style={{ top: (block.start - start) * 2, height: Math.max(30, (block.end - block.start) * 2 - 3), left: `calc(${block.column / block.columns * 100}% + ${21 - block.column / block.columns * 18}px)`, width: `calc(${100 / block.columns}% - ${6 + 18 / block.columns}px)` }}
          aria-label={`${block.appointment.patient_name}, ${dayLabel(day)}, ${clock(block.appointment.start_time)} a ${clock(block.appointment.end_time)}, ${appointmentTypes[block.appointment.type]}, ${appointmentStatuses[block.appointment.status]}`}
          aria-pressed={block.appointment.id === selectedId} aria-controls="agenda-appointment-detail"
          onClick={event => onSelect(block.appointment, event.currentTarget)}>
          <span className="agenda-event-time">{clock(block.appointment.start_time)}–{clock(block.appointment.end_time)}</span>
          <strong>{block.appointment.patient_name}</strong><span className="agenda-event-status">{appointmentTypes[block.appointment.type]} · {appointmentStatuses[block.appointment.status]}</span>
        </button>)}
      </section>)}
    </div>
  </div></>;
}
