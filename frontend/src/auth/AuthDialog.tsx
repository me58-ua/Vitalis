import { useNavigate } from 'react-router-dom';
import { useRef, useState, type FormEvent } from 'react';
import { useAuth } from './AuthContext';
import { register } from '../api/auth';
import { errorMessage } from '../api/errors';
import { apiConfigured } from '../api/client';
import { Modal } from '../components/Modal';
import type { Registration } from '../types/api';

export type AuthMode = 'login' | 'patient' | 'professional';

export function AuthDialog({ mode, onClose, onModeChange }: {
  mode: AuthMode; onClose: () => void; onModeChange: (mode: AuthMode) => void;
}) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const locked = useRef(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const isLogin = mode === 'login';
  const professional = mode === 'professional';
  const title = isLogin ? 'Iniciar sesión' : professional ? 'Crear cuenta profesional' : 'Crear cuenta de paciente';

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current) return;
    locked.current = true;
    setSubmitting(true); setError('');
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? '');
    try {
      if (isLogin) {
        await signIn(text('identifier'), text('password'));
        onClose();
      } else {
        const payload: Registration = {
          role: professional ? 'professional' : 'patient',
          name: text('name'), dni: text('dni'), username: text('username'),
          email: text('email'), password: text('password'), tel: text('tel'),
          birth_date: text('birth_date'), timezone: 'Europe/Madrid', terms_accepted: form.has('terms_accepted'),
          ...(professional ? {
            specialty: text('specialty'), bio: text('bio'), practice_address: text('practice_address'),
            practice_phone: text('practice_phone'), license_number: text('license_number'),
            default_consultation_duration_minutes: Number(text('duration')),
            telehealth_enabled: form.has('telehealth_enabled'),
            is_accepting_new_patients: form.has('is_accepting_new_patients'),
          } : {}),
        };
        await register(payload);
        setSuccess(professional
          ? 'Cuenta creada. Un administrador debe aprobar tu cuenta antes de que puedas iniciar sesión.'
          : 'Tu cuenta se ha creado. Ya puedes iniciar sesión.');
      }
    } catch (error: unknown) { setError(errorMessage(error)); }
    finally { locked.current = false; setSubmitting(false); }
  }

  return <Modal title={title} onClose={onClose} busy={submitting}>
    {success ? <div className="success-state" role="status"><p>{success}</p>
      <button className="button primary" onClick={() => navigate('/login')}>Ir a iniciar sesión</button></div>
      : <>
        <p className="muted">{isLogin ? 'Accede con tu correo electrónico o nombre de usuario.' : 'Los campos marcados con * son obligatorios.'}</p>
        {!apiConfigured && <p className="error-state" role="alert">La conexión con el servidor no está configurada. Consulta la guía de instalación.</p>}
        <form onSubmit={(event) => { void submit(event); }} aria-busy={submitting}>
          <fieldset disabled={submitting || !apiConfigured} className="form-grid">
            {isLogin ? <label className="full">Correo electrónico o usuario *<input name="identifier" autoComplete="username" required maxLength={320} /></label>
              : <>
                <label className="full">Nombre completo *<input name="name" autoComplete="name" required maxLength={150} /></label>
                <label>DNI / NIE *<input name="dni" required minLength={5} maxLength={20} /></label>
                <label>Nombre de usuario *<input name="username" autoComplete="username" required minLength={3} maxLength={50} /></label>
                <label className="full">Correo electrónico *<input name="email" type="email" autoComplete="email" required maxLength={320} /></label>
                <label>Teléfono *<input name="tel" type="tel" autoComplete="tel" required maxLength={32} /></label>
                <label>Fecha de nacimiento *<input name="birth_date" type="date" autoComplete="bday" required /></label>
              </>}
            <label className="full">Contraseña *<input name="password" type="password" autoComplete={isLogin ? 'current-password' : 'new-password'}
              required minLength={isLogin ? 1 : 8} maxLength={128} aria-describedby={isLogin ? undefined : 'password-help'} /></label>
            {!isLogin && <p id="password-help" className="field-help full">Utiliza entre 8 y 128 caracteres.</p>}
            {professional && <>
              <label>Especialidad *<input name="specialty" required maxLength={150} /></label>
              <label>Número de colegiación *<input name="license_number" required maxLength={50} /></label>
              <label className="full">Presentación profesional *<textarea name="bio" required maxLength={500} rows={3} /></label>
              <label className="full">Dirección de consulta *<input name="practice_address" required maxLength={255} /></label>
              <label>Teléfono de consulta *<input name="practice_phone" type="tel" required maxLength={50} /></label>
              <label>Duración de consulta (minutos) *<input name="duration" type="number" required min={1} step={1} defaultValue={30} /></label>
              <label className="checkbox full"><input name="telehealth_enabled" type="checkbox" />Ofrezco teleconsultas</label>
              <label className="checkbox full"><input name="is_accepting_new_patients" type="checkbox" />Acepto nuevos pacientes</label>
            </>}
            {!isLogin && <label className="checkbox full"><input name="terms_accepted" type="checkbox" required />Acepto las condiciones de uso *</label>}
            <button className="button primary full" type="submit">{submitting ? 'Enviando…' : isLogin ? 'Iniciar sesión' : 'Crear cuenta'}</button>
          </fieldset>
          {error && <p className="error-state" role="alert">{error}</p>}
          {isLogin && <p className="field-help">La sesión se conserva mientras esta página permanezca abierta. Al recargar tendrás que volver a identificarte.</p>}
        </form>
        <div className="dialog-footer">{isLogin ? <button className="text-button" disabled={submitting} onClick={() => onModeChange('patient')}>¿No tienes cuenta? Regístrate</button>
          : <button className="text-button" disabled={submitting} onClick={() => navigate('/login')}>Ya tengo una cuenta</button>}</div>
      </>}
  </Modal>;
}
