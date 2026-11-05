import { Link } from 'react-router-dom';
import { listVideoAppointments, consultationError } from '../../api/consultations';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { appointmentDate, appointmentStatuses } from '../../components/AppointmentSummary';
import { madridDay } from '../../utils/agenda';
import '../../styles/videoconsulta.css';

export function VideoConsultationsIndexPage() {
  const state = useAdminQuery(listVideoAppointments, consultationError);
  return <main id="contenido" className="consultation-main"><header className="consultation-heading"><div><p className="admin-eyebrow">ATENCIÓN A DISTANCIA</p><h1>Videoconsultas</h1><p>Selecciona una cita confirmada para acceder, aunque su hora prevista ya haya pasado.</p></div><Link className="button secondary" to="/professionalDashboard/agenda">Ver agenda</Link></header>
    {state.loading && <p role="status">Cargando videoconsultas…</p>}{state.error && <div className="error-state" role="alert"><p>{state.error}</p><button onClick={state.retry}>Reintentar</button></div>}
    {state.data && <>{state.data.length === 0 && <p>No tienes videoconsultas confirmadas sin finalizar.</p>}<ul className="consultation-list">{state.data.map(item => <li key={item.id}><div><h2>{item.patient_name}</h2><p>{appointmentDate(item.start_time)} · {appointmentStatuses[item.status]}</p><p>{item.appointment_reason || 'Motivo no indicado'}</p></div><Link className="button primary" to={`/professionalDashboard/videoconsulta/${encodeURIComponent(item.id)}?fecha=${madridDay(item.start_time)}`}>Atender videoconsulta</Link></li>)}</ul></>}
  </main>;
}
