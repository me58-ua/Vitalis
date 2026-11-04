import { useEffect } from 'react';
import { Navigate, useLocation, useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { BenefitCards } from '../components/BenefitCards';
import { PrivacyBanner } from '../components/PrivacyBanner';
import hero from '../assets/figma/imgHeroVisual.png';
import arrow from '../assets/figma/imgContainer1.svg';
import loginArrow from '../assets/figma/imgContainer2.svg';
import analysisIcon from '../assets/figma/imgContainer.svg';

export function HomePage() {
  const [params] = useSearchParams();
  const mode = params.get('acceso');
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  useEffect(() => {
    if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
  }, [location.hash]);
  function open(mode: 'login' | 'patient' | 'professional') { navigate(mode === 'login' ? '/login' : `/register?role=${mode}`); }
  if (mode === 'login') return <Navigate to="/login" replace />;
  if (mode === 'patient' || mode === 'professional') return <Navigate to={`/register?role=${mode}`} replace />;
  return <main id="contenido">
    <section className="hero section-container" aria-labelledby="hero-heading">
      <div className="hero-copy"><span className="eyebrow"><span />SALUD Y ATENCIÓN CONECTADAS</span>
        <h1 id="hero-heading">Tu salud,<br /><span>mejor comprendida<br />con tecnología.</span></h1>
        <p className="hero-description">vitaLis te ayuda a conocer mejor tu salud y tus hábitos, con evaluaciones orientativas y comunicación con profesionales en un mismo lugar.</p>
        {user ? <div className="signed-in-state"><p>Hola, <strong>{user.name}</strong>.</p><p>Has iniciado sesión. Puedes consultar tus notificaciones desde la cabecera.</p>
          <a className="button primary" href="#servicios">Conocer los servicios</a></div>
          : <><div className="hero-actions"><button className="button primary" onClick={() => open('patient')}>Registrarse como Paciente <img src={arrow} alt="" /></button>
            <button className="button secondary" onClick={() => open('professional')}>Registrarse como Médico</button></div>
            <p className="login-prompt"><span>¿YA TIENES UNA CUENTA?</span><button className="text-button" onClick={() => open('login')}>Iniciar Sesión <img src={loginArrow} alt="" /></button></p></>}
      </div>
      <div className="hero-visual"><img className="hero-photo" src={hero} alt="Un profesional y una paciente conversan en una consulta luminosa" fetchPriority="high" />
        <div className="analysis-badge"><span className="analysis-icon"><img src={analysisIcon} alt="" /></span><span><small>CONOCE TU SALUD</small><strong>Información para cuidarte</strong></span></div>
      </div>
    </section>
    <BenefitCards /><PrivacyBanner />
  </main>;
}
