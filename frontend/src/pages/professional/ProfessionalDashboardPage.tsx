import { useCallback, useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { getProfessionalDashboard } from '../../api/professional';
import { professionalError } from '../../api/professionalErrors';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { Modal } from '../../components/Modal';
import { ProfessionalAppointmentDetails, ProfessionalCreateDialog, ProfessionalHistoryDialog, ProfessionalPatientsDialog } from '../../components/ProfessionalPanels';
import { appointmentDate, appointmentStatuses, appointmentTypes } from '../../components/AppointmentSummary';
import type { ProfessionalAppointment, ProfessionalDashboard } from '../../types/api';
import calendar from '../../assets/figma/professional/calendar.svg';
import increase from '../../assets/figma/professional/increase.svg';
import arrow from '../../assets/figma/professional/arrow.svg';
import more from '../../assets/figma/professional/more.svg';
import inPerson from '../../assets/figma/professional/in-person.svg';
import video from '../../assets/figma/professional/video-type.svg';
import newAppointment from '../../assets/figma/professional/new.svg';
import patients from '../../assets/figma/professional/patients.svg';
import history from '../../assets/figma/professional/history.svg';
import messages from '../../assets/figma/professional/messages.svg';

function dayLabel(value: string, weekday = false) {
  const date = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return 'Fecha no disponible';
  return new Intl.DateTimeFormat('es-ES', { ...(weekday ? { weekday: 'short' } : { day: '2-digit', month: '2-digit', year: 'numeric' }), timeZone: 'Europe/Madrid' }).format(date);
}

function WeeklyChart({ data }: { data: ProfessionalDashboard }) {
  const max = Math.max(1, ...data.weekly_distribution.map(day => day.count));
  return <section className="professional-weekly" aria-labelledby="professional-week-title"><h2 id="professional-week-title">Distribución semanal</h2><p>{dayLabel(data.week_start)} — {dayLabel(data.week_end)}</p>
    <figure><figcaption className="professional-sr-only">Número de citas por día, sin citas canceladas. Zona horaria Europe/Madrid.</figcaption><ol className="professional-chart">{data.weekly_distribution.map(day => <li key={day.date} className={day.date === data.date ? 'is-today' : ''} aria-label={`${dayLabel(day.date)}: ${day.count} citas`}><span className="professional-chart-count">{day.count}</span><div className="professional-chart-track"><span style={{ height: `${day.count / max * 100}%` }} /></div><time dateTime={day.date}>{dayLabel(day.date, true)}</time></li>)}</ol></figure>
    <p className="field-help">Citas de lunes a domingo, sin canceladas. Europe/Madrid.</p>{data.weekly_distribution.every(day => day.count === 0) && <p>No hay citas esta semana.</p>}
  </section>;
}

function AppointmentDialog({ item, onClose, onChanged }: { item: ProfessionalAppointment; onClose: () => void; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  return <Modal title="Detalle de cita" onClose={onClose} busy={busy}><ProfessionalAppointmentDetails item={item} onBusy={setBusy} onChanged={onChanged} /></Modal>;
}

export function ProfessionalDashboardPage() {
  const [params, setParams] = useSearchParams();
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<ProfessionalAppointment | null>(null);
  const [success, setSuccess] = useState('');
  const panel = params.get('panel');
  const load = useCallback((signal: AbortSignal) => { void revision; return getProfessionalDashboard(signal); }, [revision]);
  const state = useAdminQuery(load, professionalError);
  const data = state.data;
  const close = () => setParams({}, { replace: true });
  function changed(message: string) { close(); setSelected(null); setSuccess(message); setRevision(value => value + 1); }
  const difference = data ? data.appointments_today - data.appointments_yesterday : 0;
  if (panel === 'profile') return <Navigate to="/professionalDashboard/perfil" replace />;
  if (panel === 'appointments') return <Navigate to="/professionalDashboard/agenda" replace />;
  return <main id="contenido" className="professional-main">
    <div className="professional-grid"><div className="professional-primary">
      <section className="professional-welcome"><h1>Panel del profesional</h1>{data ? <p>Resumen de tu actividad. Tienes {data.scheduled_today} {data.scheduled_today === 1 ? 'cita confirmada' : 'citas confirmadas'} para hoy, {dayLabel(data.date)}.</p> : <p>Consulta tu actividad, tus próximas citas y la distribución de la semana.</p>}</section>
      {success && <p className="success-state" role="status">{success}</p>}
      {state.loading && <p role="status">Cargando actividad profesional…</p>}
      {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
      {data && <><section className="professional-stats" aria-label="Resumen de actividad"><article><span className="professional-stat-icon"><img src={calendar} alt="" /></span><div><h2>Citas de hoy</h2><p className="professional-stat-value">{data.appointments_today}</p><p className="professional-stat-change">{difference > 0 && <img src={increase} alt="" />}{difference === 0 ? 'Igual que ayer' : `${Math.abs(difference)} ${difference > 0 ? 'más' : 'menos'} que ayer`}</p></div></article><article><span className="professional-stat-icon professional-stat-completed" aria-hidden="true">✓</span><div><h2>Completadas hoy</h2><p className="professional-stat-value">{data.completed_today}</p><p>Consultas finalizadas</p></div></article><article><span className="professional-stat-icon professional-stat-patients"><img src={patients} alt="" /></span><div><h2>Pacientes vinculados</h2><p className="professional-stat-value">{data.assigned_patients}</p><Link to="/professionalDashboard/misPacientes">Ver mis pacientes</Link></div></article></section>
      <section className="professional-upcoming" aria-labelledby="professional-appointments-title"><header><h2 id="professional-appointments-title">Próximas citas</h2><Link to="/professionalDashboard/agenda">Ver todas <img src={arrow} alt="" /></Link></header>
        {data.upcoming_appointments.length === 0 ? <p className="professional-empty">No tienes próximas citas confirmadas.</p> : <table className="professional-appointments-table"><caption className="professional-sr-only">Citas confirmadas, incluidas las que están en curso. Fechas y horas en Europe/Madrid.</caption><thead><tr><th scope="col">Paciente</th><th scope="col">Fecha y hora</th><th scope="col">Motivo</th><th scope="col">Tipo y estado</th><th scope="col">Acción</th></tr></thead><tbody>{data.upcoming_appointments.map(item => <tr key={item.id}><th scope="row"><div className="professional-patient-cell"><span className="professional-initials" aria-hidden="true">{item.patient_name.trim().split(/\s+/).slice(0, 2).map(word => Array.from(word)[0] ?? '').join('').toLocaleUpperCase('es')}</span><span><strong>{item.patient_name}</strong><small>@{item.patient_username}</small></span></div></th><td data-label="Fecha y hora"><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time></td><td data-label="Motivo">{item.appointment_reason || 'Motivo no indicado'}</td><td data-label="Tipo y estado"><span className="professional-type"><img src={item.type === 'video' ? video : inPerson} alt="" />{appointmentTypes[item.type]}</span><span className="professional-status">{appointmentStatuses[item.status]}</span></td><td data-label="Acción"><button className="professional-more" aria-label={`Ver cita de ${item.patient_name}`} onClick={() => { setSuccess(''); setSelected(item); }}><img src={more} alt="" /></button></td></tr>)}</tbody></table>}
        <footer><span>{data.upcoming_total} {data.upcoming_total === 1 ? 'cita confirmada' : 'citas confirmadas'}</span><button className="text-button professional-refresh" onClick={state.retry}>Actualizar</button></footer>
      </section></>}
    </div><aside className="professional-secondary" aria-label="Acciones y distribución semanal"><section className="professional-quick"><h2>Acciones rápidas</h2><div><Link to="?panel=new" className="professional-new"><img src={newAppointment} alt="" />Nueva cita</Link><Link to="/professionalDashboard/misPacientes"><img src={patients} alt="" />Mis pacientes</Link><Link to="/professionalDashboard/chats"><img src={messages} alt="" />Chat</Link><Link to="?panel=history"><img src={history} alt="" />Historial</Link></div></section>{data && <WeeklyChart data={data} />}</aside></div>
    {panel === 'new' && <ProfessionalCreateDialog onClose={close} onCreated={() => changed('Cita creada correctamente. Si no aparece en el resumen, consulta la agenda.')} />}
    {panel === 'patients' && <ProfessionalPatientsDialog onClose={close} />}
    {panel === 'history' && <ProfessionalHistoryDialog onClose={close} />}
    {selected && <AppointmentDialog item={selected} onClose={() => setSelected(null)} onChanged={() => changed('Cita cancelada correctamente. Se ha conservado el motivo original.')} />}
  </main>;
}
