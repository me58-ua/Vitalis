import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { createAdminAppointment, cancelAdminAppointment, getAdminAppointments } from '../../api/admin';
import { errorMessage } from '../../api/errors';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { AdminUserSelect, type UserOption } from '../../components/AdminUserSelect';
import { Modal } from '../../components/Modal';
import { appointmentDate, appointmentStatuses, appointmentTypes } from '../../components/AppointmentSummary';
import type { AppointmentQuery, AppointmentSummary, CreateAppointment } from '../../types/api';

function appointmentError(error: unknown) {
  return axios.isAxiosError(error) && error.response?.status === 409
    ? 'La cita entra en conflicto con otra reserva. Revisa el horario e inténtalo de nuevo.' : errorMessage(error);
}

function CreateAppointmentDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [patient, setPatient] = useState<UserOption | null>(null);
  const [professional, setProfessional] = useState<UserOption | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const locked = useRef(false);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current) return;
    const form = new FormData(event.currentTarget);
    const start = new Date(String(form.get('start_time'))), end = new Date(String(form.get('end_time')));
    if (!patient || !professional || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      setError('Selecciona paciente y profesional y un horario con final posterior al inicio.'); return;
    }
    const value = form.get('type');
    if (value !== 'video' && value !== 'in_person') return;
    const payload: CreateAppointment = { patient_id: patient.id, professional_id: professional.id,
      start_time: start.toISOString(), end_time: end.toISOString(), type: value };
    locked.current = true; setBusy(true); setError('');
    const abort = new AbortController(); controller.current = abort;
    try { await createAdminAppointment(payload, abort.signal); if (!abort.signal.aborted) onCreated(); }
    catch (error: unknown) { if (!abort.signal.aborted) setError(appointmentError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  return <Modal title="Crear cita" onClose={onClose} busy={busy}><form className="admin-appointment-form" aria-busy={busy} onSubmit={event => { void submit(event); }}>
    <fieldset className="form-grid" disabled={busy}>
      <AdminUserSelect role="patient" value={patient} onChange={setPatient} required disabled={busy} />
      <AdminUserSelect role="professional" value={professional} onChange={setProfessional} required disabled={busy} />
      <label>Inicio *<input name="start_time" type="datetime-local" required /></label><label>Fin *<input name="end_time" type="datetime-local" required /></label>
      <p className="field-help full">Introduce el horario en la zona de tu navegador ({Intl.DateTimeFormat().resolvedOptions().timeZone}). Se enviará en UTC y se mostrará en Europe/Madrid.</p>
      <label className="full">Modalidad *<select name="type" defaultValue="video"><option value="video">Videoconsulta</option><option value="in_person">Presencial</option></select></label>
      <button type="submit" className="button primary full">{busy ? 'Creando…' : 'Crear cita'}</button>
    </fieldset>{error && <p className="error-state" role="alert">{error}</p>}
  </form></Modal>;
}

function CancelAppointmentDialog({ item, onClose, onCancelled }: { item: AppointmentSummary; onClose: () => void; onCancelled: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (locked.current) return;
    const cancellationReason = String(new FormData(event.currentTarget).get('cancellation_reason') ?? '').trim();
    locked.current = true; setBusy(true); setError('');
    const abort = new AbortController(); controller.current = abort;
    try { await cancelAdminAppointment(item.id, cancellationReason || null, abort.signal); if (!abort.signal.aborted) onCancelled(); }
    catch (error: unknown) { if (!abort.signal.aborted) setError(appointmentError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  return <Modal title="Anular cita" onClose={onClose} busy={busy}>
    <p>Vas a anular la cita de <strong>{item.patient_name}</strong> con {item.professional_name}, el {appointmentDate(item.start_time)}. El registro de la cita se conservará.</p>
    <form aria-busy={busy} onSubmit={event => { void submit(event); }}><fieldset className="form-grid" disabled={busy}>
      <label className="full">Motivo de anulación (opcional)<textarea name="cancellation_reason" rows={3} /></label>
      <button className="button primary full" type="submit">{busy ? 'Anulando…' : 'Confirmar anulación'}</button>
      <button className="text-button full" type="button" onClick={onClose}>Volver sin anular</button>
    </fieldset>{error && <p className="error-state" role="alert">{error}</p>}</form>
  </Modal>;
}

export function AdminAppointmentsPage() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState<AppointmentQuery>(() => ({ page: 1, page_size: 20, upcoming_month: params.get('upcoming_month') === 'true', from_date: params.get('from_date') || undefined, to_date: params.get('to_date') || undefined }));
  const [upcomingOnly, setUpcomingOnly] = useState(Boolean(query.upcoming_month));
  const [fromDate, setFromDate] = useState(query.from_date ?? '');
  const [toDate, setToDate] = useState(query.to_date ?? '');
  const [patient, setPatient] = useState<UserOption | null>(null);
  const [professional, setProfessional] = useState<UserOption | null>(null);
  const [validation, setValidation] = useState('');
  const [success, setSuccess] = useState('');
  const [dialog, setDialog] = useState<'create' | AppointmentSummary | null>(null);
  const load = useCallback((signal: AbortSignal) => getAdminAppointments(query, signal), [query]);
  const state = useAdminQuery(load);
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const from = String(form.get('from_date') ?? ''), to = String(form.get('to_date') ?? '');
    if (from && to && from > to) { setValidation('La fecha inicial debe ser anterior o igual a la final.'); return; }
    setValidation(''); setSuccess('');
    const upcoming = form.has('upcoming_month');
    setParams({ ...(upcoming ? { upcoming_month: 'true' } : {}), ...(from ? { from_date: from } : {}), ...(to ? { to_date: to } : {}) }, { replace: true });
    setQuery({ page: 1, page_size: 20, patient_id: patient?.id, professional_id: professional?.id, from_date: from || undefined, to_date: to || undefined, upcoming_month: upcoming });
  }
  const data = state.data;
  return <main id="contenido" className="admin-main">
    <div className="admin-page-heading"><div><p className="admin-eyebrow">ADMINISTRACIÓN</p><h1>Gestión de citas</h1></div><button className="button primary" onClick={() => { setSuccess(''); setDialog('create'); }}>Crear cita</button></div>
    <p className="admin-intro">Consulta, filtra y anula citas. Los horarios se muestran en Europe/Madrid.</p>
    {success && <p className="success-state" role="status">{success}</p>}
    <section className="admin-card" aria-labelledby="appointment-filters"><h2 id="appointment-filters">Filtrar citas</h2>
      <form className="admin-appointment-filters" onSubmit={apply} onReset={() => { setPatient(null); setProfessional(null); setUpcomingOnly(false); setFromDate(''); setToDate(''); setValidation(''); setParams({}, { replace: true }); setQuery({ page: 1, page_size: 20 }); }}>
        <AdminUserSelect role="patient" value={patient} onChange={setPatient} />
        <AdminUserSelect role="professional" value={professional} onChange={setProfessional} />
        <label>Desde<input name="from_date" type="date" value={fromDate} onChange={event => setFromDate(event.target.value)} /></label><label>Hasta<input name="to_date" type="date" value={toDate} onChange={event => setToDate(event.target.value)} /></label>
        <label className="checkbox full"><input name="upcoming_month" type="checkbox" checked={upcomingOnly} onChange={event => setUpcomingOnly(event.target.checked)} />Solo próximas citas de este mes</label>
        <p className="field-help full">El intervalo incluye ambos días según Europe/Madrid. El resumen mensual excluye las citas iniciadas, anuladas o finalizadas.</p>
        <div className="admin-filter-actions full"><button className="button primary" type="submit" disabled={state.loading}>Aplicar filtros</button><button className="button secondary" type="reset" disabled={state.loading}>Limpiar filtros</button></div>
      </form>{validation && <p role="alert" className="error-state">{validation}</p>}
    </section>
    <section className="admin-card admin-audit-results" aria-labelledby="appointments-title" aria-busy={state.loading}>
      <div className="admin-list-heading"><h2 id="appointments-title">Citas</h2><button className="text-button" disabled={state.loading} onClick={state.retry}>Actualizar</button></div>
      {state.loading && <p role="status">Cargando citas…</p>}
      {state.error && <div role="alert" className="error-state"><p>{state.error}</p><button className="text-button" onClick={state.retry}>Reintentar</button></div>}
      {data && <><p role="status">{data.total} citas encontradas.</p>{data.appointments.length === 0 ? <p>No se han encontrado citas con estos filtros.</p> : <ul className="admin-appointments-list">{data.appointments.map(item => <li key={item.id}>
        <div><h3>{item.patient_name}</h3><p>Profesional: {item.professional_name}</p><p><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time> — <time dateTime={item.end_time}>{appointmentDate(item.end_time)}</time></p><p>{appointmentTypes[item.type]} · <strong>{appointmentStatuses[item.status]}</strong></p>{item.status === 'cancelled' && <p>Motivo de anulación: {item.cancellation_reason || 'No indicado'}</p>}</div>
        {(item.status === 'pending' || item.status === 'confirmed') && <button className="button secondary" onClick={() => { setSuccess(''); setDialog(item); }}>Anular cita</button>}
      </li>)}</ul>}
      <nav className="pagination" aria-label="Paginación de citas"><button disabled={data.page <= 1} onClick={() => setQuery({ ...query, page: data.page - 1 })}>Anterior</button><span>Página {data.page} de {Math.max(1, Math.ceil(data.total / data.page_size))}</span><button disabled={data.page * data.page_size >= data.total} onClick={() => setQuery({ ...query, page: data.page + 1 })}>Siguiente</button></nav></>}
    </section>
    {dialog === 'create' && <CreateAppointmentDialog onClose={() => setDialog(null)} onCreated={() => { setDialog(null); setSuccess('Cita creada correctamente. Si no aparece, revisa los filtros activos.'); state.retry(); }} />}
    {dialog && dialog !== 'create' && <CancelAppointmentDialog item={dialog} onClose={() => setDialog(null)} onCancelled={() => { setDialog(null); setSuccess('Cita anulada correctamente.'); state.retry(); }} />}
  </main>;
}
