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
  const [role, setRole] = useState<'patient' | 'professional'>(mode === 'professional' ? 'professional' : 'patient');
  const [step, setStep] = useState<1 | 2>(1);
  const professional = role === 'professional';
  const title = isLogin ? 'Iniciar sesión' : 'Crea tu cuenta';

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current) return;
    if (!isLogin && step === 1) {
      const data = new FormData(event.currentTarget);
      if (data.get('password') !== data.get('confirm_password')) { setError('Las contraseñas no coinciden.'); return; }
      setError(''); setStep(2); return;
    }
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
          birth_date: text('birth_date'), gender: text('gender') || null,
          timezone: professional ? 'Europe/Madrid' : text('timezone'), terms_accepted: form.has('terms_accepted'),
          ...(professional ? {
            specialty: text('specialty'), bio: text('bio'), practice_address: text('practice_address'),
            practice_phone: text('practice_phone'), license_number: text('license_number'),
            default_consultation_duration_minutes: Number(text('duration')),
            telehealth_enabled: form.has('telehealth_enabled'),
            is_accepting_new_patients: form.has('is_accepting_new_patients'),
          } : {
            address: text('address') || null,
            weight_kg: text('weight_kg') === '' ? null : Number(text('weight_kg')),
            height_cm: text('height_cm') === '' ? null : Number(text('height_cm')),
          }),
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
      <button className="button primary" onClick={() => { onClose(); navigate('/login'); }}>Ir a iniciar sesión</button></div>
      : <>
        {!isLogin && <p className="registration-step" role="status">Paso {step} de 2 · {step === 1 ? 'Cuenta y datos personales' : professional ? 'Datos profesionales' : 'Confirmar cuenta de paciente'}</p>}
        <p className="muted">{isLogin ? 'Accede con tu correo electrónico o nombre de usuario.' : 'Los campos marcados con * son obligatorios.'}</p>
        {!apiConfigured && <p className="error-state" role="alert">La conexión con el servidor no está configurada. Consulta la guía de instalación.</p>}
        <form onSubmit={(event) => { void submit(event); }} aria-busy={submitting}>
          <fieldset disabled={submitting || !apiConfigured} className="form-grid">
            <div className="form-grid full" hidden={!isLogin && step === 2}>
            {!isLogin && <h3 className="full">1. Datos personales</h3>}
            {isLogin ? <label className="full">Correo electrónico o usuario *<input name="identifier" autoComplete="username" required maxLength={320} /></label>
              : <>
                <label className="full">Nombre completo *<input name="name" autoComplete="name" required maxLength={150} /></label>
                <label>DNI / NIE *<input name="dni" required minLength={5} maxLength={20} /></label>
                <label>Nombre de usuario *<input name="username" autoComplete="username" required minLength={3} maxLength={50} /></label>
                <label>Fecha de nacimiento *<input name="birth_date" type="date" autoComplete="bday" required /></label>
                <label>Género (opcional)<input name="gender" maxLength={50} /></label>
                <h3 className="full">2. Contacto y acceso</h3>
                <label className="full">Correo electrónico *<input name="email" type="email" autoComplete="email" required maxLength={320} /></label>
                <label>Teléfono *<input name="tel" type="tel" autoComplete="tel" required maxLength={32} /></label>
              </>}
            <label className="full">Contraseña *<input name="password" type="password" autoComplete={isLogin ? 'current-password' : 'new-password'}
              required minLength={isLogin ? 1 : 8} maxLength={128} aria-describedby={isLogin ? undefined : 'password-help'} /></label>
            {!isLogin && <p id="password-help" className="field-help full">Utiliza entre 8 y 128 caracteres.</p>}
            {!isLogin && <>
              <label className="full">Confirmar contraseña *<input name="confirm_password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} /></label>
              <fieldset className="registration-roles full"><legend>Tipo de cuenta *</legend>
                <label><input type="radio" name="role" value="patient" checked={role === 'patient'} onChange={() => setRole('patient')} />Paciente<span>Para gestionar mi salud, hábitos y consultas.</span></label>
                <label><input type="radio" name="role" value="professional" checked={role === 'professional'} onChange={() => setRole('professional')} />Profesional<span>Para acompañar a mis pacientes.</span></label>
              </fieldset>
            </>}
            </div>
            {!isLogin && <fieldset className="form-grid full patient-registration" hidden={step !== 2 || professional} disabled={step !== 2 || professional}>
              <div className="full"><h3>Completa tu perfil</h3><p className="muted">Añade algunos detalles a tu perfil de paciente. Peso, altura y dirección son opcionales.</p></div>
              <p className="registration-step full">Rol seleccionado: Paciente</p>
              <label>Peso (kg)<input name="weight_kg" type="number" inputMode="decimal" min={25} max={400} step="any" aria-describedby="weight-help" /><span id="weight-help" className="field-help">Entre 25 y 400 kg.</span></label>
              <label>Altura (cm)<input name="height_cm" type="number" inputMode="decimal" min={100} max={250} step="any" aria-describedby="height-help" /><span id="height-help" className="field-help">Entre 100 y 250 cm.</span></label>
              <label className="full">Zona horaria<select name="timezone" defaultValue="Europe/Madrid" required><option value="Europe/Madrid">Europe/Madrid — España peninsular</option><option value="Atlantic/Canary">Atlantic/Canary — Islas Canarias</option><option value="UTC">UTC</option></select><span className="field-help">Se utiliza para mostrar las fechas y horas de tus citas.</span></label>
              <label className="full">Dirección de residencia (opcional)<input name="address" autoComplete="street-address" maxLength={255} placeholder="Calle, número, ciudad, código postal" /></label>
              <div className="registration-privacy full"><strong>Tu salud, mejor comprendida. Tus datos, protegidos.</strong><p>Conoce mejor tu salud e identifica posibles riesgos a partir de tu información y tus hábitos, con la tranquilidad de que tus datos se tratan de forma segura y confidencial.</p></div>
            </fieldset>}
            {!isLogin && step === 2 && professional && <>
              <label>Especialidad *<input name="specialty" required maxLength={150} /></label>
              <label>Número de colegiación *<input name="license_number" required maxLength={50} /></label>
              <label className="full">Presentación profesional *<textarea name="bio" required maxLength={500} rows={3} /></label>
              <label className="full">Dirección de consulta *<input name="practice_address" required maxLength={255} /></label>
              <label>Teléfono de consulta *<input name="practice_phone" type="tel" required maxLength={50} /></label>
              <label>Duración de consulta (minutos) *<input name="duration" type="number" required min={1} step={1} defaultValue={30} /></label>
              <label className="checkbox full"><input name="telehealth_enabled" type="checkbox" />Ofrezco teleconsultas</label>
              <label className="checkbox full"><input name="is_accepting_new_patients" type="checkbox" />Acepto nuevos pacientes</label>
            </>}
            {!isLogin && step === 2 && <label className="checkbox full"><input name="terms_accepted" type="checkbox" required />Acepto las condiciones de uso *</label>}
            {!isLogin && step === 2 && <button className="text-button full" type="button" onClick={() => { setStep(1); setError(''); }}>Volver a mis datos</button>}
            <button className="button primary full" type="submit">{submitting ? 'Enviando…' : isLogin ? 'Iniciar sesión' : step === 1 ? 'Siguiente' : 'Crear cuenta'}</button>
          </fieldset>
          {error && <p className="error-state" role="alert">{error}</p>}
          {isLogin && <p className="field-help">La sesión se conserva mientras esta página permanezca abierta. Al recargar tendrás que volver a identificarte.</p>}
        </form>
        <div className="dialog-footer">{isLogin ? <button className="text-button" disabled={submitting} onClick={() => onModeChange('patient')}>¿No tienes cuenta? Regístrate</button>
          : <button className="text-button" disabled={submitting} onClick={() => { onClose(); navigate('/login'); }}>Ya tengo una cuenta</button>}</div>
      </>}
  </Modal>;
}
