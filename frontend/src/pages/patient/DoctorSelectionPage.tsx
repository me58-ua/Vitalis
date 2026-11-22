import { useCallback, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { getBookingProfessionals, type DirectoryQuery } from '../../api/patientBooking';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import '../../styles/patient-booking.css';

export const doctorSelectionPath = '/patientPanel/equipoMedico';

export function DoctorSelectionPage() {
  const [query, setQuery] = useState<DirectoryQuery>({ page: 1, page_size: 12 });
  const modality = query.appointment_type ?? '';
  const load = useCallback((signal: AbortSignal) => getBookingProfessionals(query, signal), [query]);
  const state = useAdminQuery(load);
  const result = state.data;

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setQuery(previous => ({
      ...previous,
      page: 1,
      name: String(fields.get('name') ?? '').trim() || undefined,
      specialty: String(fields.get('specialty') ?? '').trim() || undefined,
    }));
  }

  return <main id="contenido" className="patient-booking">
    <header className="booking-heading">
      <div><h1>Equipo médico y especialistas</h1><p>Encuentra a un profesional por nombre o especialidad.</p></div>
      <Link className="button secondary" to="/patientPanel/misCitas">Mis próximas citas</Link>
    </header>
    <form className="booking-panel booking-search" onSubmit={search} aria-label="Buscar profesionales">
      <label>Profesional<input name="name" type="search" maxLength={100} placeholder="Nombre del profesional" /></label>
      <label>Especialidad<input name="specialty" type="search" maxLength={150} placeholder="Nombre de la especialidad" /></label>
      <label>Modalidad<select name="modality" value={modality} onChange={event => {
        const value = event.currentTarget.value;
        setQuery(previous => ({
          ...previous,
          page: 1,
          appointment_type: value === 'in_person' || value === 'video' ? value : undefined,
        }));
      }}>
        <option value="">Todas las modalidades</option>
        <option value="in_person">Presencial</option>
        <option value="video">Videoconsulta</option>
      </select></label>
      <button className="button primary" type="submit">Buscar</button>
    </form>
    {state.loading && <p role="status">Buscando profesionales…</p>}
    {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
    {result && (result.total === 0 ? <p>No hay profesionales que coincidan con la búsqueda.</p> : <>
      <p role="status">{result.total} {result.total === 1 ? 'profesional' : 'profesionales'}</p>
      <ul className="booking-doctors">
        {result.professionals.map(professional => <li className="booking-panel" key={professional.id}>
          <div className="booking-doctor-title">
            <span className="booking-initials" aria-hidden="true">{professional.name.trim().split(/\s+/).slice(0, 2).map(word => word.charAt(0)).join('').toLocaleUpperCase('es')}</span>
            <div><h2>{professional.name}</h2><p>{professional.specialty} · Col. {professional.license_number}</p></div>
          </div>
          {professional.bio && <p>{professional.bio}</p>}
          <ul className="booking-tags">
            {professional.telehealth_enabled && <li>Videoconsulta</li>}
            {professional.languages?.map(language => <li key={language}>{language}</li>)}
          </ul>
          {professional.is_accepting_new_patients
            ? <Link className="button primary" to={`${doctorSelectionPath}/${encodeURIComponent(professional.id)}/reservar${modality ? `?modalidad=${modality}` : ''}`} aria-label={`Reservar cita con ${professional.name}`}>Reservar cita</Link>
            : <p>No acepta nuevos pacientes.</p>}
        </li>)}
      </ul>
      {result.total > result.page_size && <nav className="booking-pagination" aria-label="Páginas de profesionales">
        <button className="button secondary" disabled={result.page <= 1} onClick={() => setQuery({ ...query, page: result.page - 1 })}>Anterior</button>
        <span>Página {result.page} de {Math.ceil(result.total / result.page_size)}</span>
        <button className="button secondary" disabled={result.page * result.page_size >= result.total} onClick={() => setQuery({ ...query, page: result.page + 1 })}>Siguiente</button>
      </nav>}
    </>)}
  </main>;
}
