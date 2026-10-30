import type { MonthlyMetric } from '../types/api';

export function GrowthBadge({ metric, appointments = false }: { metric: MonthlyMetric | undefined; appointments?: boolean }) {
  if (!metric) return null;
  const percent = metric.change_percent;
  const direction = percent === null ? 'new' : percent > 0 ? 'up' : percent < 0 ? 'down' : 'flat';
  const label = percent === null ? 'Sin base' : `${percent > 0 ? '+' : ''}${percent.toLocaleString('es-ES', { maximumFractionDigits: 1 })} %`;
  const description = `${appointments ? 'Citas programadas' : 'Altas de usuarios'}: ${metric.current_month} este mes frente a ${metric.previous_month} el mes anterior completo.${percent === null ? ' No se calcula porcentaje porque el mes anterior no tuvo registros.' : ''}`;
  return <span className={`admin-growth admin-growth-${direction}`} title={description} aria-label={`${label}. ${description}`}><span aria-hidden="true">{direction === 'up' || direction === 'new' ? '↗' : direction === 'down' ? '↘' : '→'}</span>{label}</span>;
}
