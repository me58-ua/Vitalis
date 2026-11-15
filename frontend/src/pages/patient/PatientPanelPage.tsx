import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { PatientDashboardLayout } from '../../layouts/PatientDashboardLayout';
import { usePatientDashboard } from '../../hooks/usePatientDashboard';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { getNotifications, markRead } from '../../api/notifications';
import { setPatientAIConsent } from '../../api/patient';
import { errorMessage } from '../../api/errors';
import { PatientRiskCards } from '../../components/PatientRiskCards';
import { PatientHabitsDialog, PatientHistoryDialog, PatientProfileDialog, PatientQueryFeedback, PatientUploadDialog, patientDate } from '../../components/PatientDashboardDialogs';
import { Modal } from '../../components/Modal';
import type { PatientProfile } from '../../types/api';
import calendar from '../../assets/figma/patient/Overlay.svg';
import upload from '../../assets/figma/patient/Container4.svg';
import habits from '../../assets/figma/patient/Container5.svg';
import history from '../../assets/figma/patient/Container7.svg';
import appointment from '../../assets/figma/patient/Container6.svg';

function PatientAlerts({ timezone }: { timezone: string }) {
  const state = useAdminQuery(getNotifications);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState('');
  const flight = useRef<AbortController | null>(null);
  useEffect(() => () => flight.current?.abort(), []);
  async function read(id: string) {
    if (flight.current) return;
    const abort = new AbortController(); flight.current = abort; setPending(id); setError('');
    try { await markRead(id, abort.signal); if (!abort.signal.aborted) state.retry(); }
    catch (failure: unknown) { if (!abort.signal.aborted) setError(errorMessage(failure)); }
    finally { if (!abort.signal.aborted) { flight.current = null; setPending(null); } }
  }
  return <aside className="patient-alerts" aria-labelledby="patient-alerts-title"><div className="patient-section-heading"><h2 id="patient-alerts-title">Alertas y notificaciones</h2><button className="text-button" onClick={state.retry} disabled={state.loading}>Actualizar</button></div><PatientQueryFeedback {...state} />
    {error && <p className="error-state" role="alert">{error}</p>}
    {state.data && (!state.data.notifications.length ? <p className="patient-empty">No tienes notificaciones.</p> : <><ul>{state.data.notifications.map(item => <li key={item.id} className={item.read_at ? 'is-read' : ''}><h3>{item.title}</h3><p>{item.message}</p><time dateTime={item.created_at}>{patientDate(item.created_at, timezone)}</time>{!item.read_at && <button className="text-button" disabled={pending !== null} onClick={() => { void read(item.id); }}>{pending === item.id ? 'Guardando…' : 'Marcar como leída'}</button>}</li>)}</ul>{state.data.next_cursor && <p className="field-help">Se muestran las 50 notificaciones más recientes.</p>}</>)}
  </aside>;
}
function PatientConsent({ profile, onSaved }: { profile: PatientProfile; onSaved: () => void }) {
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const flight = useRef<AbortController | null>(null);
  useEffect(() => () => flight.current?.abort(), []);
  async function save() {
    if (flight.current || !accepted) return;
    const abort = new AbortController(); flight.current = abort; setBusy(true); setError('');
    try { await setPatientAIConsent(true, abort.signal); if (!abort.signal.aborted) onSaved(); }
    catch (failure: unknown) { if (!abort.signal.aborted) setError(errorMessage(failure)); }
    finally { if (!abort.signal.aborted) { flight.current = null; setBusy(false); } }
  }
  return <div className="patient-empty"><h3>Activa las evaluaciones si lo deseas</h3><p>Para mostrar tus evaluaciones se necesita tu consentimiento para el procesamiento de tus datos de salud. Compartir datos con profesionales es un permiso separado.</p><p>Estado: {profile.ai_processing_consent ? 'Consentimiento registrado' : 'Sin consentimiento de evaluación'}</p><label className="patient-consent-check"><input type="checkbox" checked={accepted} disabled={busy} onChange={event => setAccepted(event.target.checked)} />Consiento el procesamiento de mis datos de salud para las evaluaciones de Vitalis.</label>{error && <p className="error-state" role="alert">{error}</p>}<button className="button primary" disabled={!accepted || busy} onClick={() => { void save(); }}>{busy ? 'Guardando…' : 'Guardar consentimiento'}</button></div>;
}
export function PatientPanelPage() {
  const { user } = useAuth();
  return user ? <PatientDashboard key={user.id} /> : null;
}
function PatientDashboard() {
  const { user } = useAuth();
  const { profile, risks, appointments } = usePatientDashboard();
  const [dialog, setDialog] = useState<'upload' | 'habits' | 'history' | 'profile' | null>(null);
  const [historyModel, setHistoryModel] = useState('');
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 15000); return () => window.clearInterval(timer); }, []);
  const timezone = profile.data?.timezone ?? 'Europe/Madrid';
  const next = appointments.data?.filter(item => item.status === 'confirmed' && Date.parse(item.end_time) >= now).sort((a, b) => Date.parse(a.start_time) - Date.parse(b.start_time))[0];
  function showHistory(model = '') { setHistoryModel(model); setDialog('history'); }
  if (!user) return null;
  return <PatientDashboardLayout onProfile={() => setDialog('profile')}><main id="contenido" className="patient-dashboard-main"><div className="patient-main-column"><section className="patient-greeting"><h1>Hola, {user.name}</h1><p>Aquí tienes tu resumen de salud y tus próximas citas.</p></section>
    <section className="patient-onboarding-entry"><h2>Tu perfil de salud</h2><p>Responde a unas preguntas y confirma cada dato para completar tu perfil de salud.</p><Link className="button primary" to="/patientPanel/onboarding">Abrir mi perfil de salud</Link></section>
    <section className="patient-next-appointment" aria-labelledby="patient-next-title"><div className="patient-next-content"><h2 id="patient-next-title"><img src={calendar} alt="" />Próxima cita</h2><PatientQueryFeedback {...appointments} />
      {appointments.data && (next ? <><h3>{next.appointment_reason || 'Consulta médica'}</h3><p>{next.professional_name}</p><p><time dateTime={next.start_time}>{patientDate(next.start_time, timezone)}</time> · {next.type === 'video' ? 'Videoconsulta' : 'Presencial'}</p><div className="patient-appointment-actions">{next.type === 'video' && now >= Date.parse(next.start_time) - 10 * 60 * 1000 && <Link className="button primary" to={`/patientPanel/videoconsulta/${encodeURIComponent(next.id)}`}>Unirme a la llamada</Link>}<Link className="button secondary" to="/patientPanel/misCitas">Ver mis citas</Link></div>{next.type === 'video' && now < Date.parse(next.start_time) - 10 * 60 * 1000 && <p className="field-help">Podrás unirte desde 10 minutos antes del inicio.</p>}</> : <><p>No tienes próximas citas confirmadas.</p><Link className="button primary" to="/patientPanel/misCitas">Ver mis citas</Link></>)}
    </div></section>
    <nav className="patient-quick-actions" aria-label="Accesos rápidos"><button onClick={() => setDialog('upload')}><span><img src={upload} alt="" /></span>Subir documentos</button><button onClick={() => setDialog('habits')}><span><img src={habits} alt="" /></span>Ver hábitos</button><button className="patient-history-action" onClick={() => showHistory()}><span><img src={history} alt="" /></span><strong>Historial de salud</strong><small>Revisar evaluaciones anteriores</small></button><Link to="/patientPanel/misCitas"><span><img src={appointment} alt="" /></span>Mis citas</Link></nav>
    <section id="evaluaciones" aria-labelledby="patient-risks-title"><div className="patient-section-heading"><h2 id="patient-risks-title">Tus evaluaciones de salud</h2><button className="text-button" onClick={() => { profile.retry(); risks.retry(); }}>Actualizar</button></div><PatientQueryFeedback {...profile} />
      {profile.data && <><PatientQueryFeedback {...risks} />{risks.data && (risks.data.ai_consent_required ? <PatientConsent profile={profile.data} onSaved={() => { profile.retry(); risks.retry(); }} /> : <PatientRiskCards results={risks.data.results} onHistory={showHistory} />)}</>}
    </section>
  </div><PatientAlerts timezone={timezone} /></main>
    {dialog === 'upload' && <PatientUploadDialog onClose={() => setDialog(null)} />}{dialog === 'habits' && <PatientHabitsDialog onClose={() => setDialog(null)} />}
    {(dialog === 'history' || dialog === 'profile') && (profile.data ? (dialog === 'history' ? <PatientHistoryDialog profile={profile.data} initialModel={historyModel} onClose={() => setDialog(null)} /> : <PatientProfileDialog user={user} profile={profile.data} onClose={() => setDialog(null)} />) : <Modal title={dialog === 'history' ? 'Historial de evaluaciones' : 'Tu perfil'} onClose={() => setDialog(null)}><PatientQueryFeedback {...profile} /></Modal>)}
  </PatientDashboardLayout>;
}
