import { Link, Navigate, useNavigate } from 'react-router-dom';
import { PatientDashboardLayout } from '../../layouts/PatientDashboardLayout';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { getOnboarding } from '../../api/onboarding';
import { PatientQueryFeedback } from '../../components/PatientDashboardDialogs';
import logo from '../../assets/vitalis-logo.png';
import '../../styles/patient-health-profile.css';

export function PatientOnboardingCompletePage() {
  const navigate = useNavigate();
  const state = useAdminQuery(getOnboarding);
  if (state.data && state.data.stage !== 'completed') return <Navigate to="/patientPanel/onboarding" replace />;
  return <PatientDashboardLayout onProfile={() => navigate('/patientPanel')}><main id="contenido" className="health-complete-main"><PatientQueryFeedback {...state} />{state.data?.stage === 'completed' && <section className="health-complete-card">
    <img src={logo} className="health-complete-logo" alt="vitaLis" /><span className="health-complete-check" aria-hidden="true">✓</span>
    <span className="health-eyebrow">TU PERFIL DE SALUD</span><h1>Tu perfil de salud está listo</h1><p>Hemos guardado los cambios que has confirmado. Las preguntas omitidas conservan los datos anteriores; si estaban vacíos, siguen vacíos.</p><p>Para añadir o cambiar información más adelante, vuelve al asistente IA desde tu perfil de salud.</p>
    <div className="health-complete-analysis"><strong>Tus análisis de riesgos, en tu panel</strong><p>Las evaluaciones pueden tardar unos instantes en estar disponibles. Podrás consultarlas en tu panel cuando estén listas. Los datos que no conoces quedarán pendientes.</p></div>
    <Link className="button primary" to="/patientPanel/perfilSalud">Ver mi perfil de salud <span aria-hidden="true">→</span></Link><Link className="text-button" to="/patientPanel#evaluaciones">Consultar mis análisis</Link>
  </section>}</main></PatientDashboardLayout>;
}
