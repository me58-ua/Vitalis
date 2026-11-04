import type { AdminMonthlyMetrics } from '../types/api';

const monthFormat = new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit', timeZone: 'UTC' });
function month(value: string) { return monthFormat.format(new Date(`${value}-01T00:00:00Z`)); }

export function AdminActivityChart({ data }: { data: AdminMonthlyMetrics }) {
  const rows = data.series;
  const highest = Math.max(1, ...rows.flatMap(item => [item.users, item.appointments]));
  const x = (index: number) => 44 + index * 492 / Math.max(1, rows.length - 1);
  const y = (value: number) => 226 - value * 180 / highest;
  const points = (key: 'users' | 'appointments') => rows.map((item, index) => `${x(index)},${y(item[key])}`).join(' ');
  return <figure className="admin-activity-chart">
    <svg viewBox="0 0 580 280" role="img" aria-labelledby="activity-chart-title activity-chart-description">
      <title id="activity-chart-title">Citas programadas y nuevas altas por mes</title><desc id="activity-chart-description">Serie mensual en Europe/Madrid. El mes actual sigue en curso. La tabla inferior contiene todos los valores.</desc>
      {[0, 0.5, 1].map(fraction => <g key={fraction}><line x1="44" x2="536" y1={y(highest * fraction)} y2={y(highest * fraction)} stroke="#e6eeff" /><text x="36" y={y(highest * fraction) + 4} textAnchor="end">{(highest * fraction).toLocaleString('es-ES', { maximumFractionDigits: 1 })}</text></g>)}
      <polyline points={points('appointments')} fill="none" stroke="#003527" strokeWidth="3" />
      <polyline points={points('users')} fill="none" stroke="#168c68" strokeWidth="3" strokeDasharray="6 4" />
      {rows.map((item, index) => <g key={item.month}><circle cx={x(index)} cy={y(item.appointments)} r="4" fill="#003527"><title>{month(item.month)}: {item.appointments} citas</title></circle><circle cx={x(index)} cy={y(item.users)} r="4" fill="#168c68"><title>{month(item.month)}: {item.users} altas</title></circle><text x={x(index)} y="254" textAnchor="middle">{month(item.month)}</text></g>)}
    </svg>
    <figcaption><span><i className="chart-appointments" />Citas programadas</span><span><i className="chart-users" />Nuevas altas</span></figcaption>
    <details><summary>Ver datos por mes</summary><div className="admin-table-scroll"><table className="admin-audit-table"><caption>Totales mensuales · Europe/Madrid</caption><thead><tr><th scope="col">Mes</th><th scope="col">Citas</th><th scope="col">Altas</th><th scope="col">Altas de pacientes</th><th scope="col">Altas de profesionales</th></tr></thead><tbody>{rows.map(item => <tr key={item.month}><th scope="row">{month(item.month)}</th><td>{item.appointments}</td><td>{item.users}</td><td>{item.patients}</td><td>{item.professionals}</td></tr>)}</tbody></table></div></details>
  </figure>;
}
