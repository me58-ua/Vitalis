import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { ConsultationStateError, consultationError, findVideoAppointment, getChatRoom, getPublicProfessional, joinVideo, recordVideoAttendance } from '../api/consultations';
import { jitsiOrigin } from '../api/jitsi';
import { appointmentDate, appointmentStatuses } from '../components/AppointmentSummary';
import { ConsultationChat } from '../components/ConsultationChat';
import { JitsiCall } from '../components/JitsiCall';
import { validCalendarDay } from '../utils/agenda';
import type { ProfessionalAppointment, User, VideoJoin } from '../types/api';
import '../styles/videoconsulta.css';

interface ConsultationContext { status: ProfessionalAppointment['status']; otherName: string; appointment: ProfessionalAppointment | null }
async function loadContext(appointmentId: string, role: User['role'], date: string | undefined, signal: AbortSignal): Promise<ConsultationContext> {
  if (role === 'professional') {
    const appointment = await findVideoAppointment(appointmentId, date, signal);
    if (!appointment) throw new ConsultationStateError('No se ha encontrado esta cita entre tus consultas.');
    if (appointment.type !== 'video') throw new ConsultationStateError('Esta cita no es una videoconsulta.');
    return { status: appointment.status, otherName: appointment.patient_name, appointment };
  }
  const room = await getChatRoom(appointmentId, signal);
  const professionalId = room.participants.find(item => item.role === 'professional')?.id;
  const professional = professionalId ? await getPublicProfessional(professionalId, signal) : null;
  return { status: room.status, otherName: professional?.name ?? 'Tu profesional', appointment: null };
}

export function VideoConsultationPage() {
  const { user } = useAuth();
  const { appointmentId = '' } = useParams();
  const [params] = useSearchParams();
  const value = params.get('fecha');
  const date = validCalendarDay(value) ? value : undefined;
  return user ? <Consultation key={`${user.id}:${appointmentId}`} user={user} appointmentId={appointmentId} date={date} /> : null;
}

function Consultation({ user, appointmentId, date }: { user: User; appointmentId: string; date: string | undefined }) {
  const load = useCallback((signal: AbortSignal) => loadContext(appointmentId, user.role, date, signal), [appointmentId, user.role, date]);
  const state = useAdminQuery(load, consultationError);
  const [access, setAccess] = useState<VideoJoin | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [completionPending, setCompletionPending] = useState(false);
  const [statusOverride, setStatusOverride] = useState<ConsultationContext['status'] | null>(null);
  const status = statusOverride ?? state.data?.status;
  const lock = useRef(false);
  const joined = useRef(false);
  const attendance = useRef<Promise<unknown> | null>(null);
  const lifetime = useRef(new AbortController());
  const professional = user.role === 'professional';
  const back = professional ? '/professionalDashboard/videoconsulta' : '/patientPanel/misCitas';
  useEffect(() => { const controller = new AbortController(); lifetime.current = controller; return () => controller.abort(); }, []);

  const onJoined = useCallback(() => {
    joined.current = true;
    const signal = lifetime.current.signal;
    attendance.current = recordVideoAttendance(appointmentId, 'joined', signal).catch(() => {
      if (!signal.aborted) setError('No se pudo registrar tu entrada. Se volverá a intentar al terminar tu llamada.');
    });
  }, [appointmentId]);

  const complete = useCallback(async () => {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    const signal = lifetime.current.signal;
    try {
      await attendance.current;
      // Idempotent retry also handles a failed/uncertain joined acknowledgement.
      await recordVideoAttendance(appointmentId, 'joined', signal);
      const result = await recordVideoAttendance(appointmentId, 'left', signal);
      if (signal.aborted) return;
      setStatusOverride(result.status); setCompletionPending(false); setError('');
      setNotice('Has terminado tu llamada. La cita se ha marcado como finalizada. La otra persona puede permanecer hasta terminar su propia llamada.');
    } catch (reason: unknown) {
      if (!signal.aborted) { setCompletionPending(true); setError(`Has salido, pero no se pudo guardar la finalización de la cita. ${consultationError(reason)}`); }
    } finally { if (!signal.aborted) { lock.current = false; setBusy(false); } }
  }, [appointmentId]);

  const onClosed = useCallback((intentional: boolean) => {
    setAccess(null);
    if (intentional && joined.current) { setCompletionPending(true); void complete(); }
    else setNotice(joined.current ? 'La conexión se ha cerrado. Puedes volver a entrar si la cita sigue disponible.' : 'No has llegado a unirte a la llamada.');
  }, [complete]);

  // Refresh appointment state without disposing the local iframe when the
  // other participant finishes. Their departure never closes this call.
  useEffect(() => {
    if (!access) return;
    const controller = new AbortController();
    const timer = setInterval(() => {
      void getChatRoom(appointmentId, controller.signal).then(room => {
        if (!controller.signal.aborted) setStatusOverride(room.status);
      }).catch(() => { /* The existing chat and call retain their own error states. */ });
    }, 15000);
    return () => { clearInterval(timer); controller.abort(); };
  }, [access, appointmentId]);

  async function enter() {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setNotice('');
    const signal = lifetime.current.signal;
    try {
      const result = await joinVideo(appointmentId, signal);
      if (signal.aborted) return;
      if (!result.domain || !result.room_name || !result.jwt || !Number.isFinite(Date.parse(result.expires_at)) || Date.parse(result.expires_at) <= Date.now()) throw new ConsultationStateError('No se ha recibido un acceso válido a la llamada.');
      jitsiOrigin(result.domain); joined.current = false; attendance.current = null; setAccess(result);
    } catch (reason: unknown) { if (!signal.aborted) setError(consultationError(reason)); }
    finally { if (!signal.aborted) { lock.current = false; setBusy(false); } }
  }

  return <main id="contenido" className={`consultation-main${professional ? '' : ' consultation-patient'}`}>
    <header className="consultation-heading"><div><p className="admin-eyebrow">ATENCIÓN A DISTANCIA</p><h1>Videoconsulta</h1>{state.data && <p>Con {state.data.otherName}{state.data.appointment && <> · {appointmentDate(state.data.appointment.start_time)}</>}</p>}</div><Link className="button secondary" to={back}>Volver a mis citas</Link></header>
    {state.loading && <p role="status">Cargando la consulta…</p>}
    {state.error && <div role="alert" className="error-state"><p>{state.error}</p><Link to={back}>Ver mis citas</Link><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
    {state.data && <>
      <div className="consultation-info"><span className="consultation-status">{status && appointmentStatuses[status]}</span>{state.data.appointment?.appointment_reason && <p>{state.data.appointment.appointment_reason}</p>}</div>
      {error && <div className="error-state" role="alert"><p>{error}</p>{completionPending && <button className="button secondary" disabled={busy} onClick={() => { void complete(); }}>Reintentar guardar finalización</button>}</div>}
      {notice && <p className="success-state" role="status">{notice}</p>}
      <div className="consultation-grid"><div className="consultation-video-column">
        {access ? <JitsiCall access={access} displayName={user.name} onJoined={onJoined} onClosed={onClosed} /> : <section className="consultation-prejoin" aria-label="Acceso a la videollamada">
          <div className="consultation-prejoin-mark" aria-hidden="true">◉</div><h2>{status === 'completed' ? 'Esta consulta ha finalizado' : 'Prepara tu videoconsulta'}</h2>
          {status === 'confirmed' && !completionPending ? <><p>Puedes entrar desde 10 minutos antes del inicio, sin límite posterior por la hora prevista de fin. Podrás comprobar la cámara y el micrófono antes de unirte.</p><button className="button primary" disabled={busy} onClick={() => { void enter(); }}>{busy ? 'Comprobando acceso…' : 'Entrar a la videollamada'}</button></>
            : <p>{completionPending ? 'Guardando la finalización de tu llamada.' : status === 'completed' ? 'Puedes consultar los mensajes de la cita.' : 'El estado actual de la cita no permite acceder a la videollamada.'}</p>}
        </section>}
        {access && <p className="field-help">Terminar tu llamada no desconecta a la otra persona. Si ya te has unido, la cita se marcará como finalizada.</p>}
      </div>
      {(status === 'confirmed' || status === 'completed') && <ConsultationChat key={`${appointmentId}:${status}`} appointmentId={appointmentId} userId={user.id} otherName={state.data.otherName} />}
      </div>
    </>}
  </main>;
}
