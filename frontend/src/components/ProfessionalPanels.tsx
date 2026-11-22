import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { cancelProfessionalAppointment, createProfessionalAppointment, getProfessionalAppointments, getProfessionalHistory, getProfessionalPatients, getAppointmentPrescription } from '../api/professional';
import { DateTimeField } from './DateTimeField';
import { professionalError } from '../api/professionalErrors';
import { useAuth } from '../auth/AuthContext';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { Modal } from './Modal';
import { Link } from 'react-router-dom';
import { madridDay } from '../utils/agenda';
import { PrescriptionAttachment, PrescriptionDownloadButton } from './PrescriptionAttachment';
import { professionalFollowUpPath } from '../api/appointmentFollowUp';
import { CompleteInPersonAppointment } from './CompleteInPersonAppointment';
import { appointmentDate, appointmentStatuses, appointmentTypes } from './AppointmentSummary';
import type { ProfessionalAppointment, ProfessionalAppointmentCreate, ProfessionalAppointmentQuery, ProfessionalPatientPage } from '../types/api';

function QueryFeedback({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  return <>{loading && <p role="status">Cargando datos…</p>}{error && <div className="error-state" role="alert"><p>{error}</p><button className="text-button" onClick={retry}>Reintentar</button></div>}</>;
}
function Pages({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (value: number) => void }) {
  return <nav className="pagination professional-pages" aria-label="Paginación"><button disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</button><span>Página {page} de {Math.max(1, Math.ceil(total / size))}</span><button disabled={page * size >= total} onClick={() => onPage(page + 1)}>Siguiente</button></nav>;
}

export function ProfessionalPatientsDialog({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState({ search: '', page: 1 });
  const load = useCallback((signal: AbortSignal) => getProfessionalPatients(query.search, query.page, signal), [query]);
  const state = useAdminQuery(load, professionalError);
  return <Modal title="Mis pacientes" onClose={onClose}><form className="professional-search-form" onSubmit={event => { event.preventDefault(); setQuery({ search: String(new FormData(event.currentTarget).get('search') ?? '').trim(), page: 1 }); }}><label>Buscar por nombre, correo o usuario<input name="search" maxLength={100} /></label><button className="button secondary" type="submit">Buscar</button></form>
    <QueryFeedback {...state} />{state.data && <><p>{state.data.total} pacientes asignados.</p><ul className="professional-patient-list">{state.data.patients.map(patient => <li key={patient.id}><strong>{patient.name}</strong><span>@{patient.username}</span><span>{patient.email}</span><span>{patient.tel || 'Teléfono no indicado'}</span></li>)}</ul>{state.data.patients.length === 0 && <p>No se han encontrado pacientes asignados con esta búsqueda.</p>}<Pages page={state.data.page} size={state.data.page_size} total={state.data.total} onPage={page => setQuery({ ...query, page })} /></>}
  </Modal>;
}

function PatientSelect({ disabled, onChange }: { disabled: boolean; onChange: (id: string) => void }) {
  const [query, setQuery] = useState({ search: '', page: 1 });
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<ProfessionalPatientPage['patients'][number] | null>(null);
  const load = useCallback((signal: AbortSignal) => getProfessionalPatients(query.search, query.page, signal), [query]);
  const state = useAdminQuery(load, professionalError);
  const rows = state.data?.patients ?? [];
  return <div className="professional-patient-select full"><label>Paciente asignado *<select name="patient_id" required disabled={disabled || state.loading || Boolean(state.error)} value={selected?.id ?? ''} onChange={event => {
    const patient = rows.find(item => item.id === event.target.value) ?? (selected?.id === event.target.value ? selected : null);
    setSelected(patient); onChange(patient?.id ?? '');
  }}><option value="">{state.loading ? 'Cargando pacientes…' : 'Selecciona un paciente'}</option>{selected && !rows.some(item => item.id === selected.id) && <option value={selected.id}>{selected.name}</option>}{rows.map(patient => <option key={patient.id} value={patient.id}>{patient.name} (@{patient.username})</option>)}</select></label>
    <div className="professional-search-form"><label>Buscar paciente<input value={search} maxLength={100} disabled={disabled} onChange={event => setSearch(event.target.value)} /></label><button type="button" className="text-button" disabled={disabled || state.loading} onClick={() => setQuery({ search: search.trim(), page: 1 })}>Buscar</button></div>
    {state.loading && <p role="status">Cargando pacientes…</p>}{state.error && <div className="error-state" role="alert"><p>{state.error}</p><button type="button" className="text-button" onClick={state.retry} disabled={disabled}>Reintentar</button></div>}
    {state.data && <><p className="field-help">{rows.length ? `${state.data.total} pacientes asignados encontrados.` : 'No se han encontrado pacientes asignados.'}</p><div className="professional-select-pages"><button type="button" disabled={disabled || query.page <= 1} onClick={() => setQuery({ ...query, page: query.page - 1 })}>Anterior</button><span>Página {query.page}</span><button type="button" disabled={disabled || query.page * state.data.page_size >= state.data.total} onClick={() => setQuery({ ...query, page: query.page + 1 })}>Siguiente</button></div></>}
  </div>;
}

export function ProfessionalCreateDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { user } = useAuth();
  const [patient, setPatient] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const locked = useRef(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (locked.current || !user) return;
    const values = new FormData(event.currentTarget);
    const start = new Date(String(values.get('start_time') ?? ''));
    const end = new Date(String(values.get('end_time') ?? ''));
    const type = values.get('type');
    if (!patient) { setError('Selecciona un paciente asignado a tu cuenta profesional.'); return; }
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) { setError('Introduce fechas y horas válidas. La hora de fin debe ser posterior al inicio.'); return; }
    if (type !== 'video' && type !== 'in_person') { setError('Selecciona una modalidad válida: presencial o videoconsulta.'); return; }
    const payload: ProfessionalAppointmentCreate = { patient_id: patient, start_time: start.toISOString(), end_time: end.toISOString(), type,
      appointment_reason: String(values.get('appointment_reason') ?? '').trim() || null };
    locked.current = true; setBusy(true); setError('');
    const abort = new AbortController(); controller.current = abort;
    try { await createProfessionalAppointment(user.id, payload, abort.signal); if (!abort.signal.aborted) onCreated(); }
    catch (error: unknown) { if (!abort.signal.aborted) setError(professionalError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  return <Modal title="Nueva cita" onClose={onClose} busy={busy}><form className="professional-create-form" noValidate aria-busy={busy} onSubmit={event => { void submit(event); }}><fieldset className="form-grid" disabled={busy}>
    <PatientSelect disabled={busy} onChange={setPatient} />
    <label>Inicio *<DateTimeField name="start_time" type="datetime-local" required /></label><label>Fin *<DateTimeField name="end_time" type="datetime-local" required /></label>
    <p className="field-help full">Introduce las horas en la zona de tu navegador ({Intl.DateTimeFormat().resolvedOptions().timeZone}). Se enviarán en UTC y se mostrarán en Europe/Madrid.</p>
    <label className="full">Modalidad *<select name="type" defaultValue="in_person"><option value="in_person">Presencial</option><option value="video">Videoconsulta</option></select></label>
    <label className="full">Motivo de la cita (opcional)<textarea name="appointment_reason" rows={3} /></label>
    <button className="button primary full" type="submit">{busy ? 'Guardando…' : 'Crear cita'}</button>
  </fieldset>{error && <p ref={errorRef} tabIndex={-1} className="error-state" role="alert">{error}</p>}</form></Modal>;
}

export function ProfessionalAppointmentDetails({ item, onBusy, onChanged, onOpenRecord }: { item: ProfessionalAppointment; onBusy: (busy: boolean) => void; onChanged: () => void; onOpenRecord?: () => void }) {
  const { user } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [prescriptionOpen, setPrescriptionOpen] = useState(false);
  const [prescriptionFocus, setPrescriptionFocus] = useState(0);
  const professionalId = user?.id ?? '';
  const loadPrescription = useCallback((signal: AbortSignal) => professionalId
    ? getAppointmentPrescription(professionalId, item.patient_id, item.id, signal)
    : Promise.resolve(null), [professionalId, item.patient_id, item.id]);
  const prescription = useAdminQuery(loadPrescription, professionalError);
  const prescriptionButton = useRef<HTMLButtonElement>(null);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function cancel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (locked.current || !user) return;
    const reason = String(new FormData(event.currentTarget).get('cancellation_reason') ?? '').trim();
    locked.current = true; setBusy(true); onBusy(true); setError('');
    const abort = new AbortController(); controller.current = abort;
    try { await cancelProfessionalAppointment(user.id, item.id, reason || null, abort.signal); if (!abort.signal.aborted) onChanged(); }
    catch (error: unknown) { if (!abort.signal.aborted) setError(professionalError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  return <div className="professional-appointment-details"><h3>{item.patient_name}</h3><p>@{item.patient_username}</p><p><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time> — <time dateTime={item.end_time}>{appointmentDate(item.end_time)}</time></p><p>{appointmentTypes[item.type]} · <strong>{appointmentStatuses[item.status]}</strong></p><p><strong>Motivo de la cita:</strong> {item.appointment_reason || 'Motivo no indicado'}</p>{item.status === 'cancelled' && <p><strong>Motivo de cancelación:</strong> {item.cancellation_reason || 'No indicado'}</p>}
    {!prescriptionOpen && <div className="appointment-prescription-summary">
      {prescription.loading && <p role="status">Comprobando si la cita tiene receta…</p>}
      {prescription.error && <div className="error-state" role="alert"><p>{prescription.error}</p><button type="button" className="button secondary" onClick={prescription.retry}>Reintentar</button></div>}
      {prescription.data && <div className="prescription-current"><p>Esta cita ya tiene una receta vinculada.</p><PrescriptionDownloadButton professionalId={professionalId} appointmentId={item.id} /></div>}
    </div>}
    <div className="professional-appointment-actions">
    {onOpenRecord && <button className="button secondary appointment-record-action" type="button" disabled={busy} onClick={event => { event.currentTarget.focus(); onOpenRecord(); }}>Abrir expediente del paciente</button>}
    {item.status === 'completed' && <Link className="button secondary" to={professionalFollowUpPath(item.id)}>Seguimiento de la cita</Link>}
    {user && item.type === 'in_person' && item.status === 'confirmed' && Date.parse(item.start_time) <= Date.now() && !confirming && <CompleteInPersonAppointment appointmentId={item.id} professionalId={user.id} busy={busy} onBusy={value => { setBusy(value); onBusy(value); }} />}
    {(item.status === 'completed' || item.status === 'confirmed') && <button ref={prescriptionButton} type="button" className="button secondary prescription-link-action" disabled={item.status !== 'completed' || busy} aria-expanded={prescriptionOpen} onClick={() => { setPrescriptionOpen(true); setPrescriptionFocus(value => value + 1); }}>Vincular receta</button>}
    {item.status === 'confirmed' && item.type === 'video' && <Link className="button primary" to={`/professionalDashboard/videoconsulta/${encodeURIComponent(item.id)}?fecha=${madridDay(item.start_time)}`}>Atender videoconsulta</Link>}
    {(item.status === 'confirmed') && (!confirming ? <button className="button professional-cancel" disabled={busy} onClick={() => setConfirming(true)}>Cancelar cita</button> : <form aria-busy={busy} onSubmit={event => { void cancel(event); }}><fieldset className="form-grid" disabled={busy}><p className="full">Confirma que quieres cancelar esta cita. El motivo original de la cita se conservará.</p><label className="full">Motivo de cancelación (opcional)<textarea name="cancellation_reason" rows={3} /></label><button className="button professional-cancel" type="submit">{busy ? 'Cancelando…' : 'Confirmar cancelación'}</button><button className="button secondary" type="button" onClick={() => setConfirming(false)}>Volver</button></fieldset>{error && <p className="error-state" role="alert">{error}</p>}</form>)}
    </div>
    {item.status === 'confirmed' && <p className="field-help">Podrás vincular una receta cuando la cita esté finalizada.</p>}
    {prescriptionOpen && user && item.status === 'completed' && <PrescriptionAttachment focusRequest={prescriptionFocus} professionalId={user.id} appointment={item} onBusy={onBusy} onSaved={prescription.retry} onCancel={() => { setPrescriptionOpen(false); prescriptionButton.current?.focus(); }} />}
  </div>;
}

export function ProfessionalAppointmentsDialog({ onClose, onChanged }: { onClose: () => void; onChanged: () => void }) {
  const [query, setQuery] = useState<ProfessionalAppointmentQuery>({ page: 1, page_size: 20, upcoming_only: true });
  const [selected, setSelected] = useState<ProfessionalAppointment | null>(null);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState('');
  const load = useCallback((signal: AbortSignal) => getProfessionalAppointments(query, signal), [query]);
  const state = useAdminQuery(load, professionalError);
  return <Modal title={selected ? 'Detalle de cita' : 'Agenda de citas'} onClose={onClose} busy={busy}>{selected ? <><ProfessionalAppointmentDetails item={selected} onBusy={setBusy} onChanged={onChanged} /><button className="text-button" disabled={busy} onClick={() => setSelected(null)}>Volver a la agenda</button></> : <>
    <form className="form-grid professional-agenda-filters" onSubmit={event => {
      event.preventDefault(); const values = new FormData(event.currentTarget);
      const from = String(values.get('from_date') ?? ''), to = String(values.get('to_date') ?? ''), status = values.get('status');
      if (from && to && from > to) { setValidation('La fecha inicial debe ser anterior o igual a la final.'); return; }
      const selectedStatus = status === 'confirmed' || status === 'cancelled' || status === 'completed' || status === 'no_show' || status === 'noshow_professional' ? status : undefined;
      setValidation(''); setQuery({ page: 1, page_size: 20, from_date: from || undefined, to_date: to || undefined, status: selectedStatus, upcoming_only: values.has('upcoming_only') });
    }}><label>Desde<DateTimeField name="from_date" type="date" /></label><label>Hasta<DateTimeField name="to_date" type="date" /></label><label className="full">Estado<select name="status"><option value="">Todos</option>{Object.entries(appointmentStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="checkbox full"><input type="checkbox" name="upcoming_only" defaultChecked />Solo próximas citas confirmadas</label><p className="field-help full">Fechas en Europe/Madrid. Desmarca «Solo próximas citas» para consultar citas canceladas o finalizadas.</p><button type="submit" className="button secondary full">Aplicar</button></form>
    {validation && <p className="error-state" role="alert">{validation}</p>}<QueryFeedback {...state} />{state.data && <><ul className="professional-agenda-list">{state.data.appointments.map(item => <li key={item.id}><strong>{item.patient_name}</strong><p>{appointmentDate(item.start_time)}</p><p>{appointmentTypes[item.type]} · {appointmentStatuses[item.status]}</p><p>Motivo: {item.appointment_reason || 'Motivo no indicado'}</p><button className="text-button" onClick={() => setSelected(item)}>Ver detalles</button></li>)}</ul>{state.data.appointments.length === 0 && <p>No hay citas con estos filtros.</p>}<Pages page={state.data.page} size={state.data.page_size} total={state.data.total} onPage={page => setQuery({ ...query, page })} /></>}
  </>}</Modal>;
}

export function ProfessionalHistoryDialog({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const load = useCallback((signal: AbortSignal) => user ? getProfessionalHistory(user.id, page, signal) : Promise.reject(new Error('No hay sesión')), [user, page]);
  const state = useAdminQuery(load, professionalError);
  return <Modal title="Historial de citas" onClose={onClose}><QueryFeedback {...state} />{state.data && <><ul className="professional-agenda-list">{state.data.appointments.map(item => <li key={item.id}><strong>{item.patient_name}</strong><p>{appointmentDate(item.start_time)}</p><p>{appointmentStatuses[item.status]} · {appointmentTypes[item.type]}</p><p>Motivo: {item.appointment_reason || 'Motivo no indicado'}</p>{item.status === 'cancelled' && <p>Motivo de cancelación: {item.cancellation_reason || 'No indicado'}</p>}</li>)}</ul>{state.data.appointments.length === 0 && <p>No hay citas anteriores registradas.</p>}<Pages page={state.data.page} size={state.data.page_size} total={state.data.total} onPage={setPage} /></>}</Modal>;
}
