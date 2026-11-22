import { useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { destination } from '../auth/destination';
import { Modal } from '../components/Modal';
import { HomePage } from './HomePage';
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
  const navigate = useNavigate();
  const locked = useRef(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const navigationState: unknown = useLocation().state;
  const authenticationRequired = typeof navigationState === 'object' && navigationState !== null && 'authenticationRequired' in navigationState && navigationState.authenticationRequired === true;
  const registeredRole = typeof navigationState === 'object' && navigationState !== null && 'registeredRole' in navigationState
    ? navigationState.registeredRole : undefined;
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

  return <><HomePage /><Modal title="Iniciar sesión" onClose={() => navigate('/', { replace: true })} busy={submitting || busy}>
      <div className="login-card">
        <p className="login-eyebrow">BIENVENIDO A VITALIS</p>
        {(registeredRole === 'patient' || registeredRole === 'professional') && <p className="success-state" role="status">
          {registeredRole === 'professional'
            ? 'Cuenta creada. Un administrador debe aprobar tu cuenta antes de que puedas iniciar sesión.'
            : 'Tu cuenta se ha creado. Ya puedes iniciar sesión.'}
        </p>}
        {authenticationRequired && !error && <p className="error-state" role="alert">Inicia sesión para continuar. Si tu sesión ha caducado o tu cuenta está inactiva, tendrás que identificarte de nuevo o contactar con la administración.</p>}
        {!apiConfigured && <p className="error-state" role="alert">La conexión con el servidor no está configurada. Consulta la guía de instalación.</p>}
        <form onSubmit={(event) => { void submit(event); }} aria-busy={submitting || busy}>
          <fieldset disabled={submitting || busy || !apiConfigured}>
            <label htmlFor="login-identifier">Correo electrónico o nombre de usuario</label>
            <div className="login-input"><img src={identifierIcon} alt="" /><input id="login-identifier" name="identifier" autoComplete="username" required placeholder="Introduce tu correo o usuario" /></div>
            <label htmlFor="login-password">Contraseña</label>
            <div className="login-input"><img src={passwordIcon} alt="" /><input id="login-password" name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" required placeholder="Introduce tu contraseña" />
              <button className="login-visibility" type="button" aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={visible} onClick={() => setVisible(!visible)}><img src={visibilityIcon} alt="" /></button>
            </div>
            <p className="login-session-note">Tu sesión se conserva al recargar esta pestaña. Puedes usar cuentas distintas en pestañas separadas.</p>
            <button type="submit" className="button primary login-submit">{submitting || busy ? 'Iniciando sesión…' : 'Iniciar sesión en vitaLis'}<img src={arrowIcon} alt="" /></button>
          </fieldset>
          {error && <p ref={errorRef} tabIndex={-1} className="error-state" role="alert">{error}</p>}
        </form>
        <p className="login-recovery-note"><Link to="/forgot-password">¿Has olvidado tu contraseña?</Link></p>
        <div className="login-registration"><p><img src={registerIcon} alt="" />¿Aún no tienes cuenta?</p><Link to="/register">Crear cuenta →</Link></div>
      </div>
    </Modal></>;
}
