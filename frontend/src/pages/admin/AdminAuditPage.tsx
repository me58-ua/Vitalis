import { useCallback, useState, type FormEvent } from 'react';
import { getAudits } from '../../api/admin';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import type { AuditQuery } from '../../types/api';

const uuidPattern = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
const roles = { admin: 'Administrador', patient: 'Paciente', professional: 'Profesional' };
const actions = { lectura: 'Lectura', creacion: 'Creación', modificacion: 'Modificación', eliminacion: 'Eliminación' };
const dateFormat = new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'Europe/Madrid' });
function date(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Fecha no disponible' : dateFormat.format(parsed);
}
function parseRole(value: string): AuditQuery['actor_role'] {
  return value === 'admin' || value === 'patient' || value === 'professional' ? value : undefined;
}
function parseAction(value: string): AuditQuery['accion'] {
  return value === 'lectura' || value === 'creacion' || value === 'modificacion' || value === 'eliminacion' ? value : undefined;
}

export function AdminAuditPage() {
  const [query, setQuery] = useState<AuditQuery>({ page: 1, page_size: 20 });
  const [validation, setValidation] = useState('');
  const load = useCallback((signal: AbortSignal) => getAudits(query, signal), [query]);
  const state = useAdminQuery(load);
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const text = (name: string) => String(values.get(name) ?? '').trim();
    const from = text('from_date') ? new Date(text('from_date')) : null;
    const to = text('to_date') ? new Date(text('to_date')) : null;
    if ((from && Number.isNaN(from.getTime())) || (to && Number.isNaN(to.getTime())) || (from && to && from > to)) {
      setValidation('Revisa el intervalo: la fecha inicial debe ser anterior o igual a la final.'); return;
    }
    setValidation('');
    setQuery({ page: 1, page_size: 20, actor_role: parseRole(text('actor_role')), accion: parseAction(text('accion')),
      actor_id: text('actor_id') || undefined, patient_id: text('patient_id') || undefined,
      entidad: text('entidad') || undefined, entidad_id: text('entidad_id') || undefined,
      from_date: from?.toISOString(), to_date: to?.toISOString() });
  }
  const data = state.data;
  return <main id="contenido" className="admin-main">
    <div className="admin-page-heading"><div><p className="admin-eyebrow">CONSULTA DE REGISTROS</p><h1>Auditoría y logs</h1></div><button className="button secondary" disabled={state.loading} onClick={state.retry}>Actualizar</button></div>
    <p className="admin-intro">Consulta las acciones registradas. Las auditorías son de solo lectura.</p>
    <section className="admin-card" aria-labelledby="audit-filters-title"><h2 id="audit-filters-title">Filtrar auditorías</h2>
      <form className="admin-audit-filters" onSubmit={apply} onReset={() => { setValidation(''); setQuery({ page: 1, page_size: 20 }); }}>
        <label>Rol del actor<select name="actor_role"><option value="">Todos</option>{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Acción<select name="accion"><option value="">Todas</option>{Object.entries(actions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Entidad<input name="entidad" maxLength={80} placeholder="Nombre exacto de entidad" /></label>
        <label>ID del actor<input name="actor_id" pattern={uuidPattern} title="Introduce un UUID válido" /></label>
        <label>ID del perfil de paciente<input name="patient_id" pattern={uuidPattern} title="Introduce un UUID válido" /></label>
        <label>ID de entidad<input name="entidad_id" pattern={uuidPattern} title="Introduce un UUID válido" /></label>
        <label>Desde<input name="from_date" type="datetime-local" step={1} /></label>
        <label>Hasta<input name="to_date" type="datetime-local" step={1} /></label>
        <p className="field-help full">Las fechas del filtro usan la zona horaria de tu navegador ({Intl.DateTimeFormat().resolvedOptions().timeZone}). Los registros se muestran en Europe/Madrid. Entidad e identificadores se comparan por coincidencia exacta.</p>
        <div className="admin-filter-actions full"><button className="button primary" type="submit" disabled={state.loading}>Aplicar filtros</button><button className="button secondary" type="reset" disabled={state.loading}>Limpiar filtros</button></div>
      </form>
      {validation && <p className="error-state" role="alert">{validation}</p>}
    </section>
    <section className="admin-card admin-audit-results" aria-labelledby="audit-results-title" aria-busy={state.loading}>
      <h2 id="audit-results-title">Registros de auditoría</h2>
      {state.loading && <p role="status">Cargando auditorías…</p>}
      {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="text-button" onClick={state.retry}>Reintentar</button></div>}
      {data && <>
        <p role="status">{data.total.toLocaleString('es-ES')} registros encontrados.</p>
        {data.items.length === 0 ? <p>No se han encontrado auditorías con estos filtros.</p> : <div className="admin-table-scroll" tabIndex={0} role="region" aria-label="Tabla de auditorías; desplaza horizontalmente para ver todas las columnas"><table className="admin-audit-table"><caption>Acciones registradas · fechas en Europe/Madrid</caption><thead><tr><th scope="col">Fecha y hora</th><th scope="col">Actor</th><th scope="col">Acción</th><th scope="col">Entidad</th><th scope="col">Perfil de paciente</th><th scope="col">ID de auditoría</th></tr></thead><tbody>
          {data.items.map((item) => <tr key={item.id}><td><time dateTime={item.fecha_hora}>{date(item.fecha_hora)}</time></td><td>{roles[item.actor_role]}<code>{item.actor_id}</code></td><td>{actions[item.accion]}</td><td>{item.entidad}<code>{item.entidad_id ?? 'Sin identificador'}</code></td><td><code>{item.patient_id ?? 'No asociado'}</code></td><td><code>{item.id}</code></td></tr>)}
        </tbody></table></div>}
        <nav className="pagination" aria-label="Paginación de auditorías"><button disabled={data.page <= 1} onClick={() => setQuery({ ...query, page: data.page - 1 })}>Anterior</button><span>Página {data.page} de {Math.max(1, Math.ceil(data.total / data.page_size))}</span><button disabled={data.page * data.page_size >= data.total} onClick={() => setQuery({ ...query, page: data.page + 1 })}>Siguiente</button></nav>
      </>}
    </section>
  </main>;
}
