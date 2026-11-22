import { useCallback, useState, type FormEvent } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { getPatientAppointmentHistory, patientAppointmentPath } from '../../api/appointmentFollowUp';
import { appointmentDate, appointmentStatuses } from '../../components/AppointmentSummary';
import { DateTimeField } from '../../components/DateTimeField';
import { PatientQueryFeedback } from '../../components/PatientDashboardDialogs';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import '../../styles/videoconsulta.css';

export function PatientAppointmentHistoryPage() {
  const { search } = useLocation();
  const [params, setParams] = useSearchParams();
  const [error, setError] = useState('');
  const load = useCallback((signal: AbortSignal) => getPatientAppointmentHistory(new URLSearchParams(search), signal), [search]);
  const state = useAdminQuery(load);
  const history = state.data;
  const doctor = params.get('doctor') ?? '';
  const from = params.get('from_date') ?? '';
  const to = params.get('to_date') ?? '';

  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const start = String(form.get('from_date') ?? '');
    const end = String(form.get('to_date') ?? '');
    if (start && end && start > end) {
      setError('La fecha final debe ser igual o posterior a la fecha inicial.');
      return;
    }
    const next = new URLSearchParams();
    for (const [key, value] of [['doctor', String(form.get('doctor') ?? '').trim()], ['from_date', start], ['to_date', end]] as const) {
      if (value) next.set(key, value);
    }
    setError('');
    setParams(next);
  }

  function changePage(page: number) {
    const next = new URLSearchParams(params);
    next.set('page', String(page));
    setParams(next);
  }

  return <main id="contenido" className="consultation-main consultation-patient">
    <header className="consultation-heading"><h1>Historial</h1></header>
    <form key={JSON.stringify([doctor, from, to])} className="appointment-history-filters" onSubmit={filter} onChange={() => { if (error) setError(''); }} aria-label="Filtrar historial de consultas">
      <label>Nombre del médico<input name="doctor" type="search" defaultValue={doctor} maxLength={100} /></label>
      <label>Fecha inicial<DateTimeField type="date" name="from_date" defaultValue={from} aria-describedby="appointment-history-date-help" /></label>
      <label>Fecha final<DateTimeField type="date" name="to_date" defaultValue={to} aria-describedby="appointment-history-date-help" /></label>
      <div className="booking-entry-actions"><button className="button primary" type="submit">Aplicar filtros</button>
        {(doctor || from || to) && <button className="button secondary" type="button" onClick={() => { setError(''); setParams({}); }}>Limpiar filtros</button>}
      </div>
      <p id="appointment-history-date-help">Introduce una sola fecha para buscar un día, o ambas para buscar un intervalo.</p>
      {error && <p role="alert" className="error-state">{error}</p>}
    </form>
    <PatientQueryFeedback {...state} />
    {history && <>
      {history.appointments.length === 0 && <p role="status">{history.total ? 'No hay citas en esta página.' : doctor || from || to ? 'No hay consultas que coincidan con los filtros.' : 'Aún no tienes citas en el historial.'}</p>}
      <ul className="consultation-list appointment-history-list">{history.appointments.map(item => {
        const summary = item.shared_diagnosis || item.shared_notes;
        return <li key={item.appointment_id}>
          <div><h2>{item.professional_name}</h2><p><time dateTime={item.start_time}>{appointmentDate(item.start_time)}</time> · {appointmentStatuses[item.status]}</p>
            <p><strong>Motivo</strong> · {item.appointment_reason || 'Sin motivo indicado'}</p>
            <p><strong>{item.shared_diagnosis ? 'Diagnóstico' : 'Resumen'}</strong> · {summary ? `${summary.slice(0, 200)}${summary.length > 200 ? '…' : ''}` : 'Sin información compartida'}</p>
          </div>
          <Link className="button secondary" to={patientAppointmentPath(item.appointment_id)} state={{ historySearch: search }}>Ver detalles de la cita</Link>
        </li>;
      })}</ul>
      {(history.total > history.page_size || history.page > 1) && <nav className="consultation-pagination" aria-label="Páginas del historial">
        <button type="button" className="button secondary" disabled={history.page <= 1} onClick={() => changePage(history.page - 1)}>Anterior</button>
        <span>Página {history.page} de {Math.max(1, Math.ceil(history.total / history.page_size))}</span>
        <button type="button" className="button secondary" disabled={history.page * history.page_size >= history.total} onClick={() => changePage(history.page + 1)}>Siguiente</button>
      </nav>}
    </>}
  </main>;
}
