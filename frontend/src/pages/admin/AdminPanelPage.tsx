import { Link } from 'react-router-dom';
import { getAdminTotals, getUpcomingAppointments } from '../../api/admin';
import { AppointmentInfo } from '../../components/AppointmentSummary';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import refresh from '../../assets/figma/admin/refresh.svg';
import users from '../../assets/figma/admin/users.svg';
import appointments from '../../assets/figma/admin/appointments.svg';

export function AdminPanelPage() {
  const state = useAdminQuery(getAdminTotals);
  const upcoming = useAdminQuery(getUpcomingAppointments);
  const metrics = [
    { label: 'Total de usuarios', value: state.data?.total, note: 'Todas las cuentas registradas' },
    { label: 'Pacientes', value: state.data?.patients, note: 'Cuentas con rol de paciente' },
    { label: 'Profesionales', value: state.data?.professionals, note: 'Cuentas con rol profesional' },
  ];
  return <main id="contenido" className="admin-main">
    <div className="admin-page-heading"><div><p className="admin-eyebrow">RESUMEN GENERAL</p><h1>Panel de Administración</h1></div>
      <button className="button primary admin-refresh" disabled={state.loading || upcoming.loading} onClick={() => { state.retry(); upcoming.retry(); }}><img src={refresh} alt="" />{state.loading || upcoming.loading ? 'Actualizando…' : 'Actualizar datos'}</button></div>
    {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="text-button" onClick={state.retry}>Reintentar</button></div>}
    <section className="admin-metrics" aria-label="Resumen de usuarios" aria-busy={state.loading}>
      {metrics.map((metric) => <article className="admin-metric" key={metric.label}><span className="admin-metric-icon"><img src={users} alt="" /></span><h2>{metric.label}</h2><p className="admin-metric-value">{state.loading ? '…' : metric.value === undefined ? '—' : metric.value.toLocaleString('es-ES')}</p><p>{metric.note}</p></article>)}
      <article className="admin-metric"><Link className="admin-metric-link" to="/adminPanel/gestionCitas?upcoming_month=true"><span className="admin-metric-icon"><img src={appointments} alt="" /></span><h2>Citas de este mes</h2><p className="admin-metric-value">{upcoming.loading ? '…' : upcoming.data?.total ?? '—'}</p><p>Próximas citas pendientes o confirmadas</p></Link></article>
    </section>
    {state.loading && <p role="status" className="admin-loading">Cargando los datos del servidor…</p>}
    <section className="admin-card admin-upcoming" aria-labelledby="upcoming-title" aria-busy={upcoming.loading}>
      <Link className="admin-upcoming-heading" to="/adminPanel/gestionCitas?upcoming_month=true"><h2 id="upcoming-title">Citas pendientes de este mes</h2><strong className="admin-metric-value">{upcoming.loading ? '…' : upcoming.data?.total ?? '—'}</strong></Link>
      <p>Próximas citas pendientes o confirmadas, hasta fin de mes · Europe/Madrid.</p>
      {upcoming.loading && <p role="status">Cargando próximas citas…</p>}
      {upcoming.error && <div role="alert" className="error-state"><p>{upcoming.error}</p><button className="text-button" onClick={upcoming.retry}>Reintentar</button></div>}
      {upcoming.data?.total === 0 && <p>No hay próximas citas este mes.</p>}
      {upcoming.data && <ul className="admin-upcoming-list">{upcoming.data.appointments.map(item => <li key={item.id}><Link to="/adminPanel/gestionCitas?upcoming_month=true"><AppointmentInfo item={item} /></Link></li>)}</ul>}
      <Link to="/adminPanel/gestionCitas">Gestionar todas las citas →</Link>
    </section>
    <div className="admin-insights"><section className="admin-card admin-activity"><h2>Crecimiento de actividad</h2><p>Consultas y nuevos registros</p><div className="admin-unavailable"><strong>Información no disponible</strong><p>El histórico de actividad todavía no está disponible.</p></div></section>
      <section className="admin-card admin-alerts"><h2>Alertas del sistema</h2><div className="admin-unavailable"><strong>Información no disponible</strong><p>Las alertas del sistema todavía no están disponibles. Puedes consultar las acciones registradas en la auditoría.</p></div><Link to="/adminPanel/auditoria">Consultar auditoría →</Link></section></div>
  </main>;
}
