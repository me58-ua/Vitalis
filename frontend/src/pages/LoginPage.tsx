import { useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { destination } from '../auth/destination';
import { AuthDialog } from '../auth/AuthDialog';
import { apiConfigured } from '../api/client';
import { errorMessage } from '../api/errors';
import identifierIcon from '../assets/figma/login/identifier.svg';
import passwordIcon from '../assets/figma/login/password.svg';
import visibilityIcon from '../assets/figma/login/visibility.svg';
import arrowIcon from '../assets/figma/login/arrow.svg';
import registerIcon from '../assets/figma/login/register.svg';
import '../styles/login.css';

export function LoginPage() {
  const { user, busy, signIn } = useAuth();
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [registerOpen, setRegisterOpen] = useState(false);
  const locked = useRef(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  if (user) return <Navigate to={destination(user.role)} replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current || busy) return;
    locked.current = true;
    setSubmitting(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      await signIn(String(form.get('identifier') ?? ''), String(form.get('password') ?? ''));
    } catch (error: unknown) {
      setError(axios.isAxiosError(error) && error.response?.status === 401
        ? 'El correo, el usuario o la contraseña no son válidos, o la cuenta no está activa.' : errorMessage(error));
      requestAnimationFrame(() => errorRef.current?.focus());
    } finally {
      locked.current = false; setSubmitting(false);
    }
  }

  return <main id="contenido" className="login-page">
    <div className="login-grid">
      <aside className="login-branding" aria-labelledby="login-privacy-title">
        <span className="login-kicker">TU ESPACIO DE SALUD</span>
        <Link to="/" className="login-wordmark" aria-label="vitaLis, inicio">vitaLis</Link>
        <h2 id="login-privacy-title">Tu salud, mejor comprendida. Tus datos, protegidos.</h2>
        <p>Conoce mejor tu salud e identifica posibles riesgos a partir de tu información y tus hábitos, con la tranquilidad de que tus datos se tratan de forma segura y confidencial.</p>
        <div className="login-branding-note"><strong>Un espacio para cuidarte</strong><p>Accede a tu cuenta de paciente o profesional.</p></div>
        <Link className="login-privacy-link" to="/#privacidad">Conoce cómo se tratan tus datos →</Link>
      </aside>
      <section className="login-card" aria-labelledby="login-title">
        <div><p className="login-eyebrow">BIENVENIDO A VITALIS</p><h1 id="login-title">Iniciar sesión</h1></div>
        {!apiConfigured && <p className="error-state" role="alert">La conexión con el servidor no está configurada. Consulta la guía de instalación.</p>}
        <form onSubmit={(event) => { void submit(event); }} aria-busy={submitting || busy}>
          <fieldset disabled={submitting || busy || !apiConfigured}>
            <label htmlFor="login-identifier">Correo electrónico o nombre de usuario</label>
            <div className="login-input"><img src={identifierIcon} alt="" /><input id="login-identifier" name="identifier" autoComplete="username" required placeholder="Introduce tu correo o usuario" /></div>
            <label htmlFor="login-password">Contraseña</label>
            <div className="login-input"><img src={passwordIcon} alt="" /><input id="login-password" name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" required placeholder="Introduce tu contraseña" />
              <button className="login-visibility" type="button" aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={visible} onClick={() => setVisible(!visible)}><img src={visibilityIcon} alt="" /></button>
            </div>
            <p className="login-session-note">La sesión se mantiene mientras esta aplicación permanezca abierta. Al recargar tendrás que volver a identificarte.</p>
            <button type="submit" className="button primary login-submit">{submitting || busy ? 'Iniciando sesión…' : 'Iniciar sesión en vitaLis'}<img src={arrowIcon} alt="" /></button>
          </fieldset>
          {error && <p ref={errorRef} tabIndex={-1} className="error-state" role="alert">{error}</p>}
        </form>
        <p className="login-recovery-note">La recuperación de contraseña todavía no está disponible en esta aplicación.</p>
        <div className="login-registration"><p><img src={registerIcon} alt="" />¿Aún no tienes cuenta?</p><button className="text-button" onClick={() => setRegisterOpen(true)}>Crear cuenta →</button></div>
        <Link className="login-back" to="/">Volver al inicio</Link>
      </section>
    </div>
    {registerOpen && <AuthDialog mode="patient" onClose={() => setRegisterOpen(false)} onModeChange={() => { setRegisterOpen(false); }} />}
  </main>;
}
