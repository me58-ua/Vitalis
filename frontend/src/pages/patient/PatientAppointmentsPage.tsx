import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getPatientAppointments } from '../../api/consultations';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { appointmentDate, appointmentStatuses, appointmentTypes } from '../../components/AppointmentSummary';
import '../../styles/videoconsulta.css';

export function PatientAppointmentsPage() {
  const [page, setPage] = useState(1);
  const [now, setNow] = useState(Date.now);
  const load = useCallback((signal: AbortSignal) => getPatientAppointments(page, signal), [page]);
  const state = useAdminQuery(load);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 15000); return () => clearInterval(timer); }, []);
  return <main id="contenido" className="consultation-main consultation-patient">
    <header className="consultation-heading"><h1>Mis citas</h1><Link className="button secondary" to="/patientPanel">Volver al panel</Link></header>
    {state.loading && <p role="status">Cargando tus citas…</p>}
    {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
    {state.data && <>
      {state.data.total === 0 ? <p>No tienes citas.</p> : <ul className="consultation-list">{state.data.appointments.map(item => {
        const ready = now >= Date.parse(item.start_time) - 10 * 60 * 1000;
        return <li key={item.id}><div><h2>{item.professional_name}</h2><p><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time></p>
          <p>{appointmentTypes[item.type]} · {appointmentStatuses[item.status]}</p>{item.appointment_reason && <p>{item.appointment_reason}</p>}</div>
          {item.type === 'video' && item.status === 'confirmed' && (ready
            ? <Link className="button primary patient-join-video" to={`/patientPanel/videoconsulta/${encodeURIComponent(item.id)}`}>Unirme a la videoconsulta</Link>
            : <p>Podrás unirte desde 10 minutos antes del inicio.</p>)}
          {item.type === 'video' && item.status === 'completed' && <Link className="button secondary" to={`/patientPanel/videoconsulta/${encodeURIComponent(item.id)}`}>Ver consulta finalizada</Link>}
          {item.type === 'video' && (item.status === 'confirmed' || item.status === 'completed') && <Link className="button secondary" to={`/patientPanel/chats?appointment=${encodeURIComponent(item.id)}`}>Chat de la videoconsulta</Link>}
        </li>;
      })}</ul>}
      <nav className="consultation-pagination" aria-label="Páginas de citas"><button className="button secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * state.data.page_size >= state.data.total} onClick={() => setPage(value => value + 1)}>Siguiente</button></nav>
    </>}
  </main>;
}
