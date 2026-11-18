import { useNotifications } from '../hooks/useNotifications';
import { useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { errorMessage } from '../api/errors';
import { dateTimeFormat as dateFormat } from '../utils/dateTime';
import bell from '../assets/figma/imgContainer17.svg';

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : dateFormat.format(date);
}

function LatePrescriptionApproval({ requestId, appointmentTime, onApproved }: {
  requestId: string; appointmentTime: string | null; onApproved: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function approve() {
    setBusy(true);
    setError('');
    try {
      await api.post(`/admin/late-prescription-requests/${encodeURIComponent(requestId)}/approve`);
      onApproved();
    } catch (reason) {
      setError(axios.isAxiosError(reason) && reason.response?.status === 409
        ? 'No se pudo vincular la receta a la cita. La solicitud sigue pendiente.'
        : errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return <div>
    {appointmentTime && <p><strong>Fecha y hora de la cita</strong> <time dateTime={appointmentTime}>{formatDate(appointmentTime)}</time></p>}
    <p>Esta autorización es un control administrativo de la justificación de la demora. No valida el contenido clínico de la receta.</p>
    <button className="button primary" type="button" disabled={busy} onClick={() => { void approve(); }}>
      {busy ? 'Autorizando…' : 'Autorizar emisión fuera de plazo'}
    </button>
    {error && <p role="alert" className="error-state">{error}</p>}
  </div>;
}

export function Notifications({ userId }: { userId: string }) {
  const state = useNotifications(userId);
  const { open } = state;
  return <div className="notifications">
    <button className="icon-button" aria-label={state.count === null ? 'Notificaciones' : `Notificaciones: ${state.count} sin leer`}
      aria-expanded={open} aria-controls="notification-panel" onClick={state.toggle}>
      <img src={bell} alt="" />{state.count !== null && state.count > 0 && <span className="notification-dot" />}
    </button>
    {open && <section className="notification-panel" id="notification-panel" aria-labelledby="notification-heading">
      <div className="panel-heading"><h2 id="notification-heading">Notificaciones</h2>
        <button className="icon-button" aria-label="Cerrar notificaciones" onClick={state.toggle}>×</button></div>
      {state.loading && <p role="status">Cargando notificaciones…</p>}
      {(state.error || state.countError) && <div role="alert" className="error-state"><p>{state.error || state.countError}</p>
        <button className="text-button" onClick={state.retry}>Reintentar</button></div>}
      {!state.loading && !state.error && state.page?.notifications.length === 0 && <p>No tienes notificaciones.</p>}
      {!state.loading && !state.error && state.page && <ul className="notification-list">
        {state.page.notifications.map((item) => <li key={item.id} className={item.read_at ? '' : 'unread'}>
          <h3>{item.title}</h3><p style={{ whiteSpace: 'pre-line' }}>{item.message}</p>
          {item.type === 'late_prescription_pending' && item.entity_id && <LatePrescriptionApproval
            requestId={item.entity_id} appointmentTime={item.scheduled_for} onApproved={state.retry} />}
          <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
          {(item.type === 'professional_registration_pending' || item.type === 'professional_profile_change_pending') &&
            <Link className="text-button" to="/adminPanel/gestionUsuarios?role=professional" onClick={state.toggle}>Revisar solicitud</Link>}
          {!item.read_at && <button className="text-button" disabled={state.pendingId !== null}
            onClick={() => { void state.read(item.id); }}>{state.pendingId === item.id ? 'Guardando…' : 'Marcar como leída'}</button>}
        </li>)}
      </ul>}
      {state.page?.next_cursor && <p className="field-help">Se muestran las 50 notificaciones más recientes.</p>}
      <button className="text-button" onClick={state.retry} disabled={state.loading}>Actualizar</button>
    </section>}
  </div>;
}
