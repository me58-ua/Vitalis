import { useCallback, useState } from 'react';
import { getProfessionalDashboard, getProfessionalPatients } from '../../api/professional';
import { professionalError } from '../../api/professionalErrors';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { PatientPages } from '../../components/PatientPages';
import { PatientRecord } from '../../components/PatientRecord';
import type { ProfessionalPatientPage } from '../../types/api';
import '../../styles/my-patients.css';

export function MyPatientsPage() {
  const [search, setSearch] = useState('');
  const [size, setSize] = useState(20);
  const [query, setQuery] = useState({ search: '', page: 1, size: 20 });
  const [selected, setSelected] = useState<ProfessionalPatientPage['patients'][number] | null>(null);
  const load = useCallback((signal: AbortSignal) => getProfessionalPatients(query.search, query.page, signal, query.size), [query]);
  const patients = useAdminQuery(load, professionalError);
  const summary = useAdminQuery(getProfessionalDashboard, professionalError);
  return <main id="contenido" className="patients-main">
    <header><p className="admin-eyebrow">DIRECTORIO CLÍNICO</p><h1>Mis pacientes</h1></header>
    <div className="patients-grid"><aside>
      <details className="patients-filters" open><summary>Filtros y búsqueda</summary>
        <form onSubmit={event => { event.preventDefault(); setQuery({ search: search.trim(), page: 1, size }); }}>
          <label>Nombre, correo o usuario<input type="search" value={search} maxLength={100} onChange={event => setSearch(event.target.value)} placeholder="Buscar pacientes…" /></label>
          <label>Resultados por página<select value={size} onChange={event => setSize(Number(event.target.value))}><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></label>
          <button className="button primary" type="submit">Aplicar filtros</button>
          <button className="button secondary" type="button" onClick={() => { setSearch(''); setSize(20); setQuery({ search: '', page: 1, size: 20 }); }}>Limpiar</button>
        </form>
      </details>
      <section className="patients-total" aria-label="Resumen"><h2>Pacientes asignados</h2>{summary.loading ? <p role="status">Cargando…</p> : summary.error ? <><p role="alert">No se pudo cargar el resumen.</p><button onClick={summary.retry}>Reintentar</button></> : <p>{summary.data?.assigned_patients}</p>}</section>
    </aside><section aria-label="Listado de pacientes" aria-busy={patients.loading}>
      {patients.loading && <p role="status">Cargando pacientes…</p>}
      {patients.error && <div role="alert" className="error-state"><p>{patients.error}</p><button onClick={patients.retry}>Reintentar</button></div>}
      {patients.data && <>{patients.data.patients.length === 0 ? <p className="patients-empty">{query.search ? 'No hay pacientes que coincidan con la búsqueda.' : 'Todavía no tienes pacientes asignados.'}</p> : <>
        <div className="patients-columns" aria-hidden="true"><span>Nombre y usuario</span><span>Contacto</span><span>Acciones</span></div>
        <ul className="patients-list">{patients.data.patients.map(patient => <li key={patient.id}>
          <div className="patients-identity"><span className="patients-avatar" aria-hidden="true">{patient.name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part.charAt(0)).join('').toLocaleUpperCase('es')}</span><div><strong>{patient.name}</strong><small>@{patient.username}</small></div></div>
          <div className="patients-contact"><span>{patient.email}</span><span>{patient.tel || 'Teléfono no indicado'}</span></div>
          <button className="button secondary" onClick={() => setSelected(patient)}>Expediente<span className="professional-sr-only"> de {patient.name}</span></button>
        </li>)}</ul></>}
        <p role="status">{patients.data.total} resultados{query.search ? ` para «${query.search}»` : ''}.</p>
        <PatientPages page={patients.data.page} size={patients.data.page_size} total={patients.data.total} onPage={page => setQuery({ ...query, page })} />
      </>}
    </section></div>
    {selected && <PatientRecord key={selected.id} patient={selected} onClose={() => setSelected(null)} />}
  </main>;
}
