import { Link } from 'react-router-dom';
import { getAdminTotals } from '../../api/admin';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import refresh from '../../assets/figma/admin/refresh.svg';
import users from '../../assets/figma/admin/users.svg';

export function AdminPanelPage() {
  const state = useAdminQuery(getAdminTotals);
  const metrics = [
    { label: 'Total de usuarios', value: state.data?.total, note: 'Todas las cuentas registradas' },
    { label: 'Pacientes', value: state.data?.patients, note: 'Cuentas con rol de paciente' },
    { label: 'Profesionales', value: state.data?.professionals, note: 'Cuentas con rol profesional' },
  ];
  return <main id="contenido" className="admin-main">
    <div className="admin-page-heading"><div><p className="admin-eyebrow">RESUMEN GENERAL</p><h1>Panel de Administración</h1></div>
      <button className="button primary admin-refresh" disabled={state.loading} onClick={state.retry}><img src={refresh} alt="" />{state.loading ? 'Actualizando…' : 'Actualizar datos'}</button></div>
    {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="text-button" onClick={state.retry}>Reintentar</button></div>}
    <section className="admin-metrics" aria-label="Resumen de usuarios" aria-busy={state.loading}>
      {metrics.map((metric) => <article className="admin-metric" key={metric.label}><span className="admin-metric-icon"><img src={users} alt="" /></span><h2>{metric.label}</h2><p className="admin-metric-value">{state.loading ? '…' : metric.value === undefined ? '—' : metric.value.toLocaleString('es-ES')}</p><p>{metric.note}</p></article>)}
    </section>
    {state.loading && <p role="status" className="admin-loading">Cargando los datos del servidor…</p>}
    <div className="admin-insights"><section className="admin-card admin-activity"><h2>Crecimiento de actividad</h2><p>Consultas y nuevos registros</p><div className="admin-unavailable"><strong>Información no disponible</strong><p>El histórico de actividad todavía no está disponible.</p></div></section>
      <section className="admin-card admin-alerts"><h2>Alertas del sistema</h2><div className="admin-unavailable"><strong>Información no disponible</strong><p>Las alertas del sistema todavía no están disponibles. Puedes consultar las acciones registradas en la auditoría.</p></div><Link to="/adminPanel/auditoria">Consultar auditoría →</Link></section></div>
  </main>;
}
