import { useNotifications } from '../hooks/useNotifications';
import bell from '../assets/figma/imgContainer17.svg';

const dateFormat = new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' });
function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : dateFormat.format(date);
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
          <h3>{item.title}</h3><p>{item.message}</p><time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
          {!item.read_at && <button className="text-button" disabled={state.pendingId !== null}
            onClick={() => { void state.read(item.id); }}>{state.pendingId === item.id ? 'Guardando…' : 'Marcar como leída'}</button>}
        </li>)}
      </ul>}
      {state.page?.next_cursor && <p className="field-help">Se muestran las 50 notificaciones más recientes.</p>}
      <button className="text-button" onClick={state.retry} disabled={state.loading}>Actualizar</button>
    </section>}
  </div>;
}
