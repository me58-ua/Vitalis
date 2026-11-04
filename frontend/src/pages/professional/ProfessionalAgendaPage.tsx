import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useProfessionalWeek } from '../../hooks/useProfessionalWeek';
import { ProfessionalAppointmentDetails } from '../../components/ProfessionalPanels';
import { ProfessionalWeekCalendar } from '../../components/ProfessionalWeekCalendar';
import { appointmentStatuses } from '../../components/AppointmentSummary';
import { addDays, dayLabel, madridDay, mondayOf, validCalendarDay } from '../../utils/agenda';
import type { ProfessionalAppointment } from '../../types/api';
import '../../styles/professional-agenda.css';

type StatusFilter = ProfessionalAppointment['status'] | 'all';

export function ProfessionalAgendaPage() {
  const [params, setParams] = useSearchParams();
  const today = madridDay();
  const requestedWeek = params.get('week');
  const week = mondayOf(validCalendarDay(requestedWeek) ? requestedWeek : today);
  const lastDay = addDays(week, 6);
  const dayCount = params.get('days') === '5' ? 5 : 7;
  const days = Array.from({ length: dayCount }, (_, index) => addDays(week, index));
  const requestedDay = params.get('day');
  const mobileDay = requestedDay && days.includes(requestedDay) ? requestedDay : days.includes(today) ? today : week;
  const [status, setStatus] = useState<StatusFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const selectedButton = useRef<HTMLButtonElement | null>(null);
  const state = useProfessionalWeek(week, lastDay);
  const filtered = state.data?.filter(item => status === 'all' || item.status === status) ?? [];
  const selected = state.data?.find(item => item.id === selectedId);
  const weekendCount = dayCount === 5 ? filtered.filter(item => madridDay(item.start_time) > addDays(week, 4)).length : 0;
  const visibleCount = filtered.filter(item => days.includes(madridDay(item.start_time))).length;

  useEffect(() => { if (selectedId) detailHeading.current?.focus(); }, [selectedId]);

  function changeWeek(day: string) {
    if (busy) return;
    setSelectedId(null); setNotice('');
    const next = new URLSearchParams(params);
    next.set('week', mondayOf(day)); next.delete('day');
    setParams(next);
  }
  function closeDetail() {
    setSelectedId(null);
    if (selectedButton.current?.isConnected) selectedButton.current.focus();
  }
  function changeStatus(value: string) {
    if (value === 'all' || value === 'pending' || value === 'confirmed' || value === 'completed' || value === 'cancelled' || value === 'no_show') {
      setStatus(value); setSelectedId(null);
    }
  }

  return <main id="contenido" className="agenda-main">
    <header className="agenda-heading"><div><p className="admin-eyebrow">ORGANIZA TU SEMANA</p><h1>Agenda</h1><p>Consulta tus citas y selecciona una para ver su detalle.</p></div><span className="agenda-timezone">Hora de Madrid</span></header>
    <section className="agenda-toolbar" aria-label="Controles de la agenda">
      <div className="agenda-week-navigation"><button type="button" className="button secondary" aria-label="Semana anterior" disabled={busy} onClick={() => changeWeek(addDays(week, -7))}>‹</button><button type="button" className="button secondary" disabled={busy} onClick={() => changeWeek(today)}>Hoy</button><button type="button" className="button secondary" aria-label="Semana siguiente" disabled={busy} onClick={() => changeWeek(addDays(week, 7))}>›</button></div>
      <h2 className="agenda-week-title" aria-live="polite">{dayLabel(week, { day: 'numeric', month: 'short' })} — {dayLabel(lastDay, { day: 'numeric', month: 'short', year: 'numeric' })}</h2>
      <label>Ir a la semana de<input type="date" name="agenda_date" value={week} disabled={busy} onChange={event => { if (validCalendarDay(event.target.value)) changeWeek(event.target.value); }} /></label>
      <label>Días visibles<select name="agenda_days" value={dayCount} disabled={busy} onChange={event => { const next = new URLSearchParams(params); next.set('days', event.target.value === '5' ? '5' : '7'); next.delete('day'); setSelectedId(null); setParams(next); }}><option value={7}>Lunes a domingo</option><option value={5}>Lunes a viernes</option></select></label>
      <label>Estado<select name="agenda_status" value={status} disabled={busy} onChange={event => changeStatus(event.target.value)}><option value="all">Todos los estados</option>{Object.entries(appointmentStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <button type="button" className="button secondary" disabled={busy || state.loading} onClick={() => { setSelectedId(null); state.retry(); }}>Actualizar</button>
    </section>
    {notice && <p className="success-state" role="status">{notice}</p>}
    <section id="agenda-appointment-detail" className="agenda-detail" hidden={!selected} aria-labelledby="agenda-detail-title">
      {selected && <><div className="agenda-detail-heading"><h2 id="agenda-detail-title" ref={detailHeading} tabIndex={-1}>Detalle de la cita</h2><button className="button secondary" disabled={busy} onClick={closeDetail}>Cerrar detalle</button></div>
        <ProfessionalAppointmentDetails key={`${selected.id}:${selected.status}`} item={selected} onBusy={setBusy} onChanged={() => { setBusy(false); setSelectedId(null); setNotice('Cita cancelada correctamente. Se ha conservado el motivo original.'); state.retry(); }} />
      </>}
    </section>
    <section aria-label="Semana de citas" aria-busy={state.loading}>
      {state.loading && <p className="agenda-feedback" role="status">Cargando la semana…</p>}
      {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button type="button" className="button secondary" onClick={state.retry}>Reintentar</button></div>}
      {state.data && <>
        <p className="agenda-count" role="status">{visibleCount} {visibleCount === 1 ? 'cita' : 'citas'} en los días visibles.{weekendCount > 0 && <> Hay {weekendCount} más durante el fin de semana. <button className="text-button" disabled={busy} onClick={() => { const next = new URLSearchParams(params); next.set('days', '7'); setParams(next); }}>Mostrar siete días</button></>}</p>
        {visibleCount === 0 && <p className="agenda-empty">{status === 'all' ? 'No hay citas en los días visibles de esta semana.' : 'No hay citas con este estado en los días visibles.'}</p>}
        <nav className="agenda-mobile-days" aria-label="Seleccionar día">{days.map(day => <button type="button" key={day} disabled={busy} aria-pressed={mobileDay === day} aria-label={dayLabel(day, { weekday: 'long', day: 'numeric', month: 'long' })} onClick={() => { const next = new URLSearchParams(params); next.set('day', day); setParams(next); }}><span>{dayLabel(day, { weekday: 'short' })}</span><strong>{dayLabel(day, { day: 'numeric' })}</strong></button>)}</nav>
        <ProfessionalWeekCalendar days={days} selectedDay={mobileDay} appointments={filtered} selectedId={selectedId} onSelect={(item, button) => { if (!busy) { selectedButton.current = button; setSelectedId(item.id); } }} />
        <p className="agenda-help">Cada línea representa 30 minutos. Los espacios sin citas no indican disponibilidad para reservar.</p>
      </>}
    </section>
  </main>;
}
