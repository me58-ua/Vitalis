import { useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { RegistrationForm } from '../auth/RegistrationForm';
import { useAuth } from '../auth/AuthContext';
import { destination } from '../auth/destination';
import brand from '../assets/figma/register/brand.svg';
import consultation from '../assets/figma/register/consultation.png';
import '../styles/register.css';

export function RegisterPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [step, setStep] = useState<1 | 2>(1);
  if (user) return <Navigate to={destination(user.role)} replace />;
  return <main id="contenido" className="register-page">
    <div className={`register-shell register-step-${step}`}>
      <aside className="register-sidebar" aria-labelledby="register-privacy-title">
        <Link to="/" className="register-brand" aria-label="vitaLis, inicio"><span><img src={brand} alt="" /></span><span>vitaLis<small>SALUD Y ATENCIÓN CONECTADAS</small></span></Link>
        <div className="register-narrative"><p className="register-eyebrow">TU ESPACIO DE SALUD</p><h2 id="register-privacy-title">Tu salud, mejor comprendida. Tus datos, protegidos.</h2><p>Conoce mejor tu salud e identifica posibles riesgos a partir de tu información y tus hábitos, con la tranquilidad de que tus datos se tratan de forma segura y confidencial.</p></div>
        <div className="register-sidebar-detail"><img className="register-photo" src={consultation} alt="Una profesional conversa con un paciente en una consulta" /><div><strong>Un perfil para ti</strong><p>Reúne tus datos personales y configura tu cuenta.</p></div><div><strong>Pacientes y profesionales</strong><p>Elige tu rol y completa los datos correspondientes.</p></div></div>
        <div className="register-sidebar-footer"><span>© vitaLis Salud Digital</span><Link to="/#privacidad">Privacidad</Link></div>
      </aside>
      <RegistrationForm initialRole={params.get('role') === 'professional' ? 'professional' : 'patient'} onStepChange={setStep} />
    </div>
    <Link className="register-home" to="/">Volver al inicio</Link>
  </main>;
}
