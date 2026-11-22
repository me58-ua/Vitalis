import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { api } from '../../api/client';
import { session } from '../../api/session';
import { professionalError } from '../../api/professionalErrors';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { ProfessionalProfileEditor } from '../../components/ProfessionalProfileEditor';
import { ProfilePhotoForm } from '../../components/ProfilePhotoForm';
import { ProfessionalWorkingHours, useWorkingHours } from '../../components/ProfessionalWorkingHours';
import { localizedValue } from '../../utils/dateTime';
import '../../styles/professional-agenda.css';

type NotificationSettings = { email_notifications_enabled: boolean };
async function loadSettings(signal: AbortSignal) {
  return (await api.get<NotificationSettings>('/professionals/me/notification-settings', { signal })).data;
}

function AccountSettings() {
  const { busy: loggingOut } = useAuth();
  const navigate = useNavigate();
  const state = useAdminQuery(loadSettings, professionalError);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const locked = useRef(false), controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function save(event: FormEvent<HTMLFormElement>, password: boolean) {
    event.preventDefault(); if (locked.current) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    if (password && values.get('new_password') !== values.get('confirm_password')) { setError('Las contraseñas no coinciden.'); return; }
    locked.current = true; setBusy(true); setError(''); setNotice('');
    const abort = new AbortController(); controller.current = abort;
    try {
      if (password) {
        await api.post('/professionals/me/change-password', { current_password: values.get('current_password'), new_password: values.get('new_password') }, { signal: abort.signal });
        if (!abort.signal.aborted) { session.replace(null); navigate('/login', { replace: true }); }
      } else {
        await api.patch('/professionals/me/notification-settings', { email_notifications_enabled: values.has('email_notifications_enabled') }, { signal: abort.signal });
        if (!abort.signal.aborted) { setNotice('Preferencias guardadas.'); state.retry(); }
      }
    } catch (error: unknown) { if (!abort.signal.aborted) setError(professionalError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  return <section className="professional-upcoming" aria-labelledby="account-settings-title"><h2 id="account-settings-title">Configuración de la cuenta</h2>
    {notice && <p role="status" className="success-state">{notice}</p>}{error && <p role="alert" className="error-state">{error}</p>}
    <h3>Notificaciones</h3><p>Las notificaciones dentro de Vitalis permanecen disponibles en la campana. Puedes configurar los avisos por correo de citas y mensajes; los correos de seguridad se mantienen.</p>
    {state.loading && <p role="status">Cargando preferencias…</p>}{state.error && <div role="alert"><p>{state.error}</p><button onClick={state.retry}>Reintentar preferencias</button></div>}
    {state.data && <form key={String(state.data.email_notifications_enabled)} onSubmit={event => { void save(event, false); }}><fieldset disabled={busy || loggingOut}><label className="checkbox"><input type="checkbox" name="email_notifications_enabled" defaultChecked={state.data.email_notifications_enabled} />Recibir avisos por correo electrónico</label><button className="button secondary">Guardar notificaciones</button></fieldset></form>}
    <h3>Cambiar contraseña</h3><p>Al cambiarla se invalidan todas tus sesiones y tendrás que volver a iniciar sesión.</p>
    <form className="form-grid" onSubmit={event => { void save(event, true); }}><fieldset className="form-grid full" disabled={busy || loggingOut}>
      <label>Contraseña actual<input type="password" name="current_password" autoComplete="current-password" required /></label>
      <label>Nueva contraseña<input type="password" name="new_password" autoComplete="new-password" required minLength={8} maxLength={128} /></label>
      <label>Confirmar nueva contraseña<input type="password" name="confirm_password" autoComplete="new-password" required minLength={8} maxLength={128} /></label>
      <button className="button primary">Cambiar contraseña</button>
    </fieldset></form>
  </section>;
}

export function ProfessionalProfilePage() {
  const workingHours = useWorkingHours();
  const { user } = useAuth();
  if (!user) return null;
  return <main id="contenido" className="professional-main professional-profile-page"><header><h1>Perfil profesional</h1><p>Gestiona tu información profesional, disponibilidad y cuenta.</p></header>
    <section className="professional-upcoming"><h2>Datos personales</h2><dl className="professional-personal"><div><dt>Nombre</dt><dd>{user.name}</dd></div><div><dt>Fecha de nacimiento</dt><dd>{localizedValue(user.birth_date, 'date')}</dd></div><div><dt>Correo de la cuenta</dt><dd>{user.email}</dd></div><div><dt>Teléfono de la cuenta</dt><dd>{user.tel}</dd></div></dl><p className="field-help">El contacto visible para pacientes se configura en los datos profesionales.</p></section>
    <section className="professional-upcoming"><h2>Información visible para pacientes</h2><ProfessionalProfileEditor /></section>
    <section className="professional-upcoming"><h2>Foto de perfil</h2><ProfilePhotoForm /></section>
    <section className="professional-upcoming"><h2>Gestión de disponibilidad</h2><ProfessionalWorkingHours state={workingHours} onBusy={() => {}} onChanged={() => {}} /><Link className="button secondary" to="/professionalDashboard/agenda">Abrir Agenda y gestionar ausencias</Link></section>
    <AccountSettings />
  </main>;
}
