import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { cancelPatientAppointment, consultationError, getPatientAppointments } from '../../api/consultations';
import { useAuth } from '../../auth/AuthContext';
import { Modal } from '../../components/Modal';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { appointmentDate, appointmentStatuses, appointmentTypes } from '../../components/AppointmentSummary';
import '../../styles/videoconsulta.css';
import { doctorSelectionPath } from './DoctorSelectionPage';
import type { PatientAppointmentPage } from '../../types/api';

const cancellationNoticeMs = 24 * 60 * 60 * 1000;

export function PatientAppointmentsPage() {
  const location = useLocation();
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [now, setNow] = useState(Date.now);
  const [selected, setSelected] = useState<PatientAppointmentPage['appointments'][number] | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState('');
  const [notice, setNotice] = useState('');
  const pending = useRef<AbortController | null>(null);
  const load = useCallback((signal: AbortSignal) => getPatientAppointments(page, signal), [page]);
  const state = useAdminQuery(load);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 15000); return () => clearInterval(timer); }, []);
  useEffect(() => () => pending.current?.abort(), []);

  async function cancel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user || !selected || pending.current) return;
    const reason = String(new FormData(event.currentTarget).get('cancellation_reason') ?? '').trim() || null;
    const request = new AbortController();
    pending.current = request;
    setCancelling(true);
    setCancelError('');
    try {
      await cancelPatientAppointment(user.id, selected.id, reason, request.signal);
      if (request.signal.aborted) return;
      setSelected(null);
      setNotice('Cita cancelada. Puedes consultarla en el historial.');
      if (page > 1 && state.data?.appointments.length === 1) setPage(page - 1);
      else state.retry();
    } catch (error) {
      if (!request.signal.aborted) setCancelError(consultationError(error));
    } finally {
      pending.current = null;
      if (!request.signal.aborted) setCancelling(false);
    }
  }
  return <main id="contenido" className="consultation-main consultation-patient">
    <header className="consultation-heading"><h1>Mis próximas citas</h1><div className="booking-entry-actions"><Link className="button primary" to={doctorSelectionPath}>Reservar cita</Link><Link className="button secondary" to="/patientPanel">Volver al panel</Link></div></header>
    {location.state?.appointmentBooked === true && <p role="status">Cita registrada.</p>}
    {notice && <p className="success-state" role="status">{notice}</p>}
    {state.loading && <p role="status">Cargando tus citas…</p>}
    {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
    {state.data && <>
      {state.data.total === 0 ? <p>No tienes próximas citas confirmadas.</p> : <ul className="consultation-list">{state.data.appointments.map(item => {
        const untilStart = Date.parse(item.start_time) - now;
        const ready = untilStart <= 10 * 60 * 1000;
        return <li key={item.id}><div><h2>{item.professional_name}</h2><p><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time></p>
          <p>{appointmentTypes[item.type]} · {appointmentStatuses[item.status]}</p>{item.appointment_reason && <p>{item.appointment_reason}</p>}</div>
          {item.type === 'video' && (ready
            ? <Link className="button primary patient-join-video" to={`/patientPanel/videoconsulta/${encodeURIComponent(item.id)}`}>Unirme a la videoconsulta</Link>
            : <p>Podrás unirte desde 10 minutos antes del inicio.</p>)}
          {item.type === 'video' && <Link className="button secondary" to={`/patientPanel/chats?appointment=${encodeURIComponent(item.id)}`}>Chat de la videoconsulta</Link>}
          {untilStart > cancellationNoticeMs && <button className="button secondary" type="button" onClick={() => { setSelected(item); setCancelError(''); setNotice(''); }}>Cancelar cita</button>}
          {untilStart > 0 && untilStart <= cancellationNoticeMs && <p className="field-help">La cancelación requiere más de 24 horas de antelación.</p>}
        </li>;
      })}</ul>}
      <nav className="consultation-pagination" aria-label="Páginas de citas"><button className="button secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * state.data.page_size >= state.data.total} onClick={() => setPage(value => value + 1)}>Siguiente</button></nav>
    </>}
    {selected && <Modal title="Cancelar cita" busy={cancelling} onClose={() => setSelected(null)}>
      <p>{selected.professional_name} · {appointmentDate(selected.start_time)}</p>
      <form onSubmit={event => { void cancel(event); }} aria-busy={cancelling}>
        <fieldset className="form-grid" disabled={cancelling}>
          <label className="full">Motivo de cancelación (opcional)<textarea name="cancellation_reason" rows={3} /></label>
          <button type="submit" className="button danger">{cancelling ? 'Cancelando…' : 'Confirmar cancelación'}</button>
          <button type="button" className="button secondary" onClick={() => setSelected(null)}>Conservar cita</button>
        </fieldset>
        {cancelError && <p role="alert" className="error-state">{cancelError}</p>}
      </form>
    </Modal>}
  </main>;
}
