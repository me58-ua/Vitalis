import { useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { requestPasswordReset, resetPassword } from '../api/auth';
import { apiConfigured } from '../api/client';
import { errorMessage } from '../api/errors';
import { Modal } from '../components/Modal';
import { HomePage } from './HomePage';
import '../styles/login.css';

export function PasswordRecoveryPage({ mode }: { mode: 'request' | 'reset' }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get('token')?.trim() ?? '';
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [invalidLink, setInvalidLink] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const requesting = mode === 'request';
  const formAvailable = requesting || (Boolean(token) && !invalidLink);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || !formAvailable) return;
    const data = new FormData(event.currentTarget);
    const password = String(data.get('password') ?? '');
    if (!requesting && password !== data.get('confirmation')) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      if (requesting) await requestPasswordReset(String(data.get('email') ?? '').trim());
      else await resetPassword(token, password);
      setDone(true);
    } catch (failure) {
      if (!requesting && axios.isAxiosError(failure) && failure.response?.status === 400) {
        setInvalidLink(true);
      } else {
        setError(errorMessage(failure));
      }
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return <><HomePage /><Modal title={requesting ? 'Recuperar contraseña' : 'Restablecer contraseña'} onClose={() => navigate('/login', { replace: true })} busy={busy}>
    <div className="login-card">
      {done ? <p role="status">{requesting
        ? 'Si el correo corresponde a una cuenta activa, recibirás un enlace de recuperación. Revisa también la carpeta de correo no deseado.'
        : 'Tu contraseña se ha actualizado. Ya puedes iniciar sesión con la nueva contraseña.'}</p>
        : formAvailable ? <form onSubmit={event => { void submit(event); }} aria-busy={busy}>
          <fieldset disabled={busy || !apiConfigured}>
            {requesting ? <><label htmlFor="recovery-email">Correo electrónico</label>
              <div className="login-input"><input id="recovery-email" name="email" type="email" autoComplete="email" maxLength={320} required /></div></>
              : <><label htmlFor="recovery-password">Nueva contraseña</label>
                <div className="login-input"><input id="recovery-password" name="password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required /></div>
                <label htmlFor="recovery-confirmation">Repite la nueva contraseña</label>
                <div className="login-input"><input id="recovery-confirmation" name="confirmation" type="password" autoComplete="new-password" minLength={8} maxLength={128} required /></div></>}
            <button className="button primary login-submit" type="submit">{busy ? 'Enviando…' : requesting ? 'Enviar enlace' : 'Guardar nueva contraseña'}</button>
          </fieldset>
          {error && <p className="error-state" role="alert">{error}</p>}
          {!apiConfigured && <p className="error-state" role="alert">La conexión con el servidor no está configurada.</p>}
        </form> : <><p className="error-state" role="alert">El enlace de recuperación no es válido o ha caducado.</p><Link to="/forgot-password">Solicitar otro enlace</Link></>}
      <Link to="/login" className="login-back">Volver a iniciar sesión</Link>
    </div>
  </Modal></>;
}
