import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { ConsultationStateError, consultationError, findVideoAppointment, getChatRoom, getPublicProfessional, joinVideo, updateConsultationStatus } from '../api/consultations';
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
  const [confirmation, setConfirmation] = useState(false);
  const [attended, setAttended] = useState(false);
  const [copied, setCopied] = useState(false);
  const lock = useRef(false);
  const request = useRef<AbortController | null>(null);
  const professional = user.role === 'professional';
  const back = professional ? '/professionalDashboard' : '/patientPanel';
  useEffect(() => () => request.current?.abort(), []);
  const onJoined = useCallback(() => setAttended(true), []);
  const onClosed = useCallback(() => { setAccess(null); setNotice('Has salido de la llamada. El estado de la cita no se ha modificado.'); }, []);

  async function perform(action: 'join' | 'complete') {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setNotice('');
    const controller = new AbortController(); request.current = controller;
    try {
      if (action === 'join') {
        const result = await joinVideo(appointmentId, controller.signal);
        if (controller.signal.aborted) return;
        if (!result.domain || !result.room_name || !result.jwt || !Number.isFinite(Date.parse(result.expires_at)) || Date.parse(result.expires_at) <= Date.now()) throw new ConsultationStateError('No se ha recibido un acceso válido a la llamada.');
        jitsiOrigin(result.domain);
        setAccess(result);
      } else {
        await updateConsultationStatus(user.id, appointmentId, 'completed', controller.signal);
        if (controller.signal.aborted) return;
        setConfirmation(false);
        setAccess(null); setNotice('Consulta marcada como finalizada. El chat se conserva como historial.');
        state.retry();
      }
    } catch (reason: unknown) { if (!controller.signal.aborted) setError(consultationError(reason)); }
    finally { if (!controller.signal.aborted) { lock.current = false; setBusy(false); } }
  }
  async function copyPatientLink() {
    try { await navigator.clipboard.writeText(`${window.location.origin}/patientPanel/videoconsulta/${encodeURIComponent(appointmentId)}`); setCopied(true); }
    catch { setCopied(false); setError('No se pudo copiar el enlace. Puedes seleccionarlo en el campo que aparece debajo.'); }
  }

  return <main id="contenido" className={`consultation-main${professional ? '' : ' consultation-patient'}`}>
    <header className="consultation-heading"><div><p className="admin-eyebrow">ATENCIÓN A DISTANCIA</p><h1>Videoconsulta</h1>{state.data && <p>Con {state.data.otherName}{state.data.appointment && <> · {appointmentDate(state.data.appointment.start_time)}</>}</p>}</div><Link className="button secondary" to={back}>Volver al panel</Link></header>
    {state.loading && <p role="status">Cargando la consulta…</p>}
    {state.error && <div role="alert" className="error-state"><p>{state.error}</p><Link to={professional ? '/professionalDashboard/videoconsulta' : back}>Ver mis opciones de acceso</Link><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
    {state.data && <>
      <div className="consultation-info"><span className="consultation-status">{appointmentStatuses[state.data.status]}</span>{state.data.appointment?.appointment_reason && <p>{state.data.appointment.appointment_reason}</p>}
        {professional && <details className="consultation-patient-link"><summary>Enlace de acceso para el paciente</summary><p>Solo el paciente de esta cita puede entrar con su cuenta.</p><label>Enlace de la consulta<input readOnly value={`${window.location.origin}/patientPanel/videoconsulta/${encodeURIComponent(appointmentId)}`} onFocus={event => event.currentTarget.select()} /></label><button className="button secondary" onClick={() => { void copyPatientLink(); }}>{copied ? 'Enlace copiado' : 'Copiar enlace del paciente'}</button></details>}
      </div>
      {error && <div className="error-state" role="alert"><p>{error}</p></div>}{notice && <p className="success-state" role="status">{notice}</p>}
      <div className="consultation-grid"><div className="consultation-video-column">
        {access ? <JitsiCall access={access} displayName={user.name} onJoined={onJoined} onClosed={onClosed} /> : <section className="consultation-prejoin" aria-label="Acceso a la videollamada">
          <div className="consultation-prejoin-mark" aria-hidden="true">◉</div><h2>{state.data.status === 'completed' ? 'Esta consulta ha finalizado' : 'Prepara tu videoconsulta'}</h2>
          {state.data.status === 'confirmed' ? <><p>Puedes entrar desde 10 minutos antes del inicio, sin límite posterior por la hora prevista de fin. Podrás comprobar la cámara y el micrófono antes de unirte.</p><button className="button primary" disabled={busy} onClick={() => { void perform('join'); }}>{busy ? 'Comprobando acceso…' : 'Entrar a la videollamada'}</button><p className="field-help">El servidor valida la cita y los permisos de acceso.</p></>
              : <p>{state.data.status === 'completed' ? 'Puedes consultar los mensajes de la cita.' : 'El estado actual de la cita no permite acceder a la videollamada.'}</p>}
        </section>}
        {professional && attended && state.data.status === 'confirmed' && <section className="consultation-completion"><p>Salir de la llamada no cambia el estado de la cita.</p><button className="button secondary" disabled={busy} onClick={() => setConfirmation(true)}>Marcar consulta finalizada</button></section>}
        {confirmation && <section className="consultation-confirmation" aria-label="Confirmar cambio de estado"><h2>Finalizar la consulta</h2><p>Confirma que la atención ha terminado. La cita pasará a finalizada y saldrás de la videollamada.</p><div><button className="button primary" disabled={busy} onClick={() => { void perform('complete'); }}>{busy ? 'Guardando…' : 'Confirmar'}</button><button className="button secondary" disabled={busy} onClick={() => setConfirmation(false)}>Volver</button></div></section>}
      </div>
      {(state.data.status === 'confirmed' || state.data.status === 'completed') && <ConsultationChat key={`${appointmentId}:${state.data.status}`} appointmentId={appointmentId} userId={user.id} otherName={state.data.otherName} />}
      </div>
    </>}
  </main>;
}
