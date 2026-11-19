import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PatientDashboardLayout } from '../../layouts/PatientDashboardLayout';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { getHealthProfile, updateHealthSharingConsent } from '../../api/healthProfile';
import { errorMessage } from '../../api/errors';
import { patientAppointmentPath } from '../../api/appointmentFollowUp';
import { AppointmentPrescriptionDownload, SharedAppointmentNotes } from './PatientAppointmentDetailPage';
import { restartOnboarding, onboardingError } from '../../api/onboarding';
import { PatientQueryFeedback, patientDate } from '../../components/PatientDashboardDialogs';
import { ProfessionalHealthSharing } from '../../components/ProfessionalHealthSharing';
import { familyConditionNames } from '../../utils/familyHistory';
import allergiesIcon from '../../assets/figma/health-profile/allergies.svg';
import medicationIcon from '../../assets/figma/health-profile/medication.svg';
import historyIcon from '../../assets/figma/health-profile/history.svg';
import biometricsIcon from '../../assets/figma/health-profile/biometrics.svg';
import habitsIcon from '../../assets/figma/health-profile/habits.svg';
import privacyIcon from '../../assets/figma/health-profile/privacy.svg';
import '../../styles/patient-health-profile.css';

function Section({ id, title, subtitle, icon, children }: { id: string; title: string; subtitle: string; icon: string; children: ReactNode }) {
  return <section className="health-section" id={id}><header><span className="health-section-icon"><img src={icon} alt="" /></span><div><h2>{title}</h2><p>{subtitle}</p></div></header>{children}</section>;
}
const number = (value: number | null | undefined) => value == null ? 'Sin registrar' : new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 }).format(value);
const habitLabels = { tabaco: 'Tabaco', ejercicio: 'Actividad física', sueno: 'Sueño', dieta: 'Fruta y verdura' };
const unitLabels = { tabaco: 'cigarrillos/día', ejercicio: 'minutos/semana', sueno: 'horas/noche', dieta: 'raciones/día' };
const alcoholOptions = ['Nunca', 'Mensualmente o menos', 'De 2 a 4 veces al mes', 'De 2 a 3 veces a la semana', '4 o más veces a la semana'];

export function PatientHealthProfilePage() {
  const navigate = useNavigate();
  const state = useAdminQuery(getHealthProfile);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');
  const [sharingBusy, setSharingBusy] = useState(false);
  const [sharingError, setSharingError] = useState('');
  const [sharingNotice, setSharingNotice] = useState('');
  const sharingRequest = useRef<AbortController | null>(null);
  const flight = useRef<AbortController | null>(null);
  useEffect(() => () => { flight.current?.abort(); sharingRequest.current?.abort(); }, []);
  async function changeSharingConsent(enabled: boolean) {
    if (sharingRequest.current) return;
    const abort = new AbortController();
    sharingRequest.current = abort;
    setSharingBusy(true);
    setSharingError('');
    setSharingNotice('');
    try {
      await updateHealthSharingConsent(enabled, abort.signal);
      if (!abort.signal.aborted) {
        state.retry();
        setSharingNotice(enabled ? 'Consentimiento general activado.' : 'Consentimiento general revocado.');
      }
    } catch (failure: unknown) {
      if (!abort.signal.aborted) setSharingError(errorMessage(failure));
    } finally {
      sharingRequest.current = null;
      if (!abort.signal.aborted) setSharingBusy(false);
    }
  }
  async function openAssistant() {
    if (flight.current) return;
    const abort = new AbortController(); flight.current = abort; setStarting(true); setStartError('');
    try {
      await restartOnboarding(abort.signal);
      if (!abort.signal.aborted) navigate('/patientPanel/onboarding');
    } catch (failure: unknown) { if (!abort.signal.aborted) setStartError(onboardingError(failure)); }
    finally { if (!abort.signal.aborted) { flight.current = null; setStarting(false); } }
  }
  const data = state.data;
  const profile = data?.profile;
  const completed = data?.onboarding_stage === 'completed';
  const empty = (key: string, none: string) => data?.declarations[key] === 'none' ? none : data?.declarations[key] === 'unknown' ? 'No lo sabes todavía. Completa este dato mediante el asistente IA cuando lo conozcas.' : 'No hay datos registrados en esta sección.';
  const latestAlcohol = data?.alcohol_current ?? data?.alcohol_logs[0];
  return <PatientDashboardLayout onProfile={() => navigate('/patientPanel')}><main id="contenido" className="health-profile-main">
    <nav className="health-breadcrumb" aria-label="Ruta de navegación"><Link to="/patientPanel">Portal del paciente</Link><span aria-hidden="true">›</span><span>Mi perfil de salud</span></nav>
    <PatientQueryFeedback {...state} />{startError && <p role="alert" className="error-state">{startError}</p>}
    {data && profile && <>
      {completed && <div className="health-saved-banner"><span aria-hidden="true">✓</span><div><strong>Tu información de salud, registrada y confirmada por ti</strong><p>Aquí puedes consultar los datos del asistente y actualizarlos cuando cambien.</p></div></div>}
      <header className="health-profile-heading"><div><span className="health-eyebrow">TU INFORMACIÓN DE SALUD</span><h1>Mi perfil de salud</h1><p>Tus datos personales de salud, reunidos en un solo lugar.</p></div><button className="button primary health-open-assistant" disabled={starting} onClick={() => { void openAssistant(); }}>{starting ? 'Abriendo…' : completed ? 'Actualizar con el asistente IA' : 'Continuar con el asistente IA'}</button></header>
      <p className="health-muted">Los datos se añaden o cambian únicamente mediante el asistente IA. Puedes omitir las preguntas sin modificar lo que ya está guardado.</p>
      <div className="health-integrity"><div><span className="health-integrity-check" aria-hidden="true">{completed ? '✓' : '○'}</span><div><strong>{completed ? 'Registro inicial completado' : 'Tu perfil está en construcción'}</strong><p>Los datos desconocidos se muestran como pendientes.</p></div></div><Link to="/patientPanel#evaluaciones">Ver mis análisis de riesgos →</Link></div>
      <div className="health-profile-grid"><div className="health-profile-column">
        <Section id="health-allergies" title="Alergias" subtitle="Alergias y gravedad que has registrado" icon={allergiesIcon}>
          {!data.allergies.length ? <p className="health-empty">{empty('allergies', 'Has indicado que no tienes alergias conocidas.')}</p> : data.allergies.map(item => <article className={`health-record severity-${item.severity}`} key={item.id}><div className="health-record-top"><h3>{item.name}</h3><span className="health-tag">Gravedad: {item.severity}</span></div><div className="health-record-bottom"><small>Dato registrado en tu perfil</small></div></article>)}
        </Section>
        <Section id="health-medications" title="Tratamientos y medicación" subtitle="Medicamentos, dosis y frecuencia declarados" icon={medicationIcon}>
          {!data.medications.length ? <p className="health-empty">{empty('medication', 'Has indicado que no tomas medicamentos actualmente.')}</p> : data.medications.map(item => <article className="health-record" key={item.id}><div className="health-record-top"><h3>{item.name}</h3><span className="health-tag">{item.active ? 'Activo' : 'Inactivo'}</span></div><dl className="health-medication-details"><div><dt>Dosis</dt><dd>{item.dosage}</dd></div><div><dt>Frecuencia</dt><dd>{item.frequency}</dd></div></dl></article>)}
        </Section>
        <Section id="health-conditions" title="Antecedentes y condiciones" subtitle="Condiciones crónicas diagnosticadas" icon={historyIcon}>
          {!data.chronic_conditions.length ? <p className="health-empty">{empty('chronic_conditions', 'Has indicado que no tienes enfermedades crónicas diagnosticadas.')}</p> : data.chronic_conditions.map(item => <article className="health-record" key={item.id}><h3>{item.condition_name}</h3><p>{item.active ? 'Activa' : 'Inactiva'} · Diagnóstico: {item.diagnosis_date ? item.diagnosis_date.split('-').reverse().join('/') : 'fecha no indicada'}</p></article>)}
          <h3 className="health-subtitle">Antecedentes médicos familiares</h3><p className="health-muted">Incluyen enfermedades que se repiten en la familia y trastornos hereditarios. No son diagnósticos personales ni confirman una enfermedad genética.</p>{!data.family_history_entries.length ? <p className="health-empty">{empty('family_history', 'Has indicado que no tienes antecedentes familiares conocidos.')}</p> : data.family_history_entries.map(item => <article className="health-record" key={item.id}><h3>{item.relative_detail || item.relationship} · {familyConditionNames[item.condition_category] ?? item.condition_category}</h3>{item.detail && <p>{item.detail}</p>}<p>Edad al diagnóstico: {item.age_at_diagnosis == null ? 'desconocida' : `${item.age_at_diagnosis} años`}</p>{item.notes && <p>Notas: {item.notes}</p>}</article>)}
        </Section>
      </div><div className="health-profile-column">
        <Section id="health-biometrics" title="Biometría basal" subtitle="Altura y peso registrados" icon={biometricsIcon}>
          <dl className="health-biometric-grid"><div><dt>Peso corporal</dt><dd>{number(profile.weight_kg)}{profile.weight_kg != null && <small> kg</small>}</dd></div><div><dt>Estatura</dt><dd>{number(profile.height_cm)}{profile.height_cm != null && <small> cm</small>}</dd></div></dl><p className="health-muted">Actualiza estas medidas mediante el asistente IA.</p>{(profile.height_cm == null || profile.weight_kg == null) && <p className="health-muted health-bmi-missing">No se puede calcular el BMI porque faltan datos de {profile.height_cm == null && profile.weight_kg == null ? 'altura y peso' : profile.height_cm == null ? 'altura' : 'peso'}.</p>}
        </Section>
        <Section id="health-habits" title="Estilo de vida y hábitos" subtitle="Los últimos valores que has registrado" icon={habitsIcon}>
          {(Object.keys(habitLabels) as (keyof typeof habitLabels)[]).map(kind => {
            const latest = data.habit_logs.filter(item => item.habit_type === kind).sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id)[0];
            return <div className="health-habit" key={kind}><div><strong>{habitLabels[kind]}</strong><p>{latest ? `${number(latest.value)} ${latest.value == null ? '' : unitLabels[kind]}` : 'Sin registrar'}</p>{latest && <small>{latest.date.split('-').reverse().join('/')}</small>}</div></div>;
          })}
          <div className="health-habit"><div><strong>Consumo de alcohol</strong><p>{latestAlcohol?.frequency != null ? alcoholOptions[latestAlcohol.frequency] : 'Sin registrar'}</p>{latestAlcohol && (latestAlcohol.frequency ?? 0) > 0 && <><p>Consumiciones por día: {latestAlcohol.quantity == null ? 'Sin registrar' : ['1 o 2', '3 o 4', '5 o 6', 'De 7 a 9', '10 o más'][latestAlcohol.quantity]}</p><p>6 o más bebidas: {latestAlcohol.binge == null ? 'Sin registrar' : ['Nunca', 'Menos de una vez al mes', 'Mensualmente', 'Semanalmente', 'A diario o casi a diario'][latestAlcohol.binge]}</p></>}</div></div>
        </Section>
        <section className="health-analysis-note"><h2>Tu perfil y tus análisis</h2><p>Las evaluaciones se muestran cuando hay información suficiente y has dado tu consentimiento. No sustituyen una valoración profesional.</p><Link to="/patientPanel#evaluaciones">Consultar análisis →</Link></section>
      </div></div>
      <Section id="health-appointment-follow-ups" title="Información compartida en tus citas" subtitle="Diagnósticos, notas clínicas y recetas de tus citas finalizadas" icon={historyIcon}>
        {data.appointment_follow_ups == null && <p className="health-empty">La información compartida de tus citas no está disponible.</p>}
        {data.appointment_follow_ups?.length === 0 && <p className="health-empty">Aún no hay información compartida sobre tus citas.</p>}
        {data.appointment_follow_ups?.map(item => <article className="health-record" key={item.appointment_id}>
          <h3>{item.professional_name}</h3><p>{patientDate(item.start_time, profile.timezone)}</p>
          <SharedAppointmentNotes appointment={item} />
          {item.has_prescription && <AppointmentPrescriptionDownload appointmentId={item.appointment_id} />}
          <Link to={patientAppointmentPath(item.appointment_id)}>Ver detalles de la cita</Link>
        </article>)}
      </Section>
      <section className="health-consent"><span className="health-section-icon"><img src={privacyIcon} alt="" /></span><div><h2>Tu consentimiento</h2><p>Procesamiento mediante IA: <strong>{profile.ai_processing_consent ? 'aceptado' : 'no aceptado'}</strong>.</p>{profile.ai_processing_consent_at && <p>Última decisión registrada: {patientDate(profile.ai_processing_consent_at, profile.timezone)}.</p>}</div></section>
      <section className="health-consent"><span className="health-section-icon"><img src={privacyIcon} alt="" /></span><div>
        <h2>Compartir mi perfil con profesionales</h2>
        <p>Consentimiento general <strong>{profile.share_health_data ? 'activo' : 'desactivado'}</strong>.</p>
        <p>Al revocarlo, se retira el acceso al perfil para todos los profesionales. Al volver a activarlo, se aplican tus elecciones de reserva guardadas. Los diagnósticos y las notas de las citas siguen en el historial.</p>
        {sharingError && <p role="alert">{sharingError}</p>}
        <button className="button secondary" disabled={sharingBusy} onClick={() => { void changeSharingConsent(!profile.share_health_data); }}>
          {sharingBusy ? 'Guardando…' : profile.share_health_data ? 'Revocar consentimiento general' : 'Activar consentimiento general'}
        </button>
        <ProfessionalHealthSharing enabled={profile.share_health_data} />
      </div></section>
    </>}
    {sharingNotice && <p role="status">{sharingNotice}</p>}
  </main></PatientDashboardLayout>;
}
