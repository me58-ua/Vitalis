import { useCallback, useState } from 'react';
import { getAppointmentUsers } from '../api/admin';
import { useAdminQuery } from '../hooks/useAdminQuery';
import type { User } from '../types/api';

export type UserOption = Pick<User, 'id' | 'name' | 'username'>;

export function AdminUserSelect({ role, value, onChange, required = false, disabled = false }: {
  role: 'patient' | 'professional'; value: UserOption | null; onChange: (value: UserOption | null) => void; required?: boolean; disabled?: boolean;
}) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState({ search: '', page: 1 });
  const load = useCallback((signal: AbortSignal) => getAppointmentUsers(role, filter.search, filter.page, signal), [role, filter]);
  const state = useAdminQuery(load);
  const label = role === 'patient' ? 'Paciente' : 'Profesional';
  const rows = state.data?.users ?? [];
  return <div className="admin-user-select">
    <label>{label}{required ? ' *' : ''}<select name={`${role}_id`} required={required} disabled={disabled || state.loading || Boolean(state.error)} value={value?.id ?? ''} onChange={(event) => {
      const selected = rows.find((item) => item.id === event.target.value);
      onChange(selected ?? (value?.id === event.target.value ? value : null));
    }}><option value="">{state.loading ? 'Cargando…' : required ? `Selecciona ${label.toLowerCase()}` : `Todos los ${role === 'patient' ? 'pacientes' : 'profesionales'}`}</option>
      {value && !rows.some(item => item.id === value.id) && <option value={value.id}>{value.name} (@{value.username})</option>}
      {rows.map(item => <option key={item.id} value={item.id} disabled={required && !item.is_active}>{item.name} (@{item.username}){!item.is_active ? ' · Inactivo' : ''}</option>)}
    </select></label>
    <div className="admin-select-search"><label>Buscar {label.toLowerCase()}<input disabled={disabled} value={search} onChange={event => setSearch(event.target.value)} maxLength={100} /></label><button type="button" disabled={disabled || state.loading} onClick={() => setFilter({ search: search.trim(), page: 1 })}>Buscar</button></div>
    {state.error && <div role="alert" className="error-state"><p>{state.error}</p><button type="button" onClick={state.retry}>Reintentar</button></div>}
    {state.data && <div className="admin-select-pages"><button type="button" disabled={disabled || filter.page === 1} onClick={() => setFilter({ ...filter, page: filter.page - 1 })}>Anterior</button><span>{filter.page} / {Math.max(1, Math.ceil(state.data.total / state.data.page_size))}</span><button type="button" disabled={disabled || filter.page * state.data.page_size >= state.data.total} onClick={() => setFilter({ ...filter, page: filter.page + 1 })}>Siguiente</button></div>}
    {!state.loading && !state.error && rows.length === 0 && <p className="field-help">No se han encontrado cuentas.</p>}
  </div>;
}
