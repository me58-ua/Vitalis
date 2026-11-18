import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getPatientFollowUp, type PatientFollowUp } from '../../api/appointmentFollowUp';
import { consultationError } from '../../api/consultations';
import { downloadMyPrescription } from '../../api/patient';
import { appointmentDate } from '../../components/AppointmentSummary';
import { PatientQueryFeedback } from '../../components/PatientDashboardDialogs';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import '../../styles/videoconsulta.css';

export function SharedAppointmentNotes({ appointment }: { appointment: PatientFollowUp }) {
  return <>
    {appointment.shared_diagnosis && <div><h3>Diagnóstico</h3><p className="appointment-note-text">{appointment.shared_diagnosis}</p></div>}
    {appointment.shared_notes && <div><h3>Notas clínicas</h3><p className="appointment-note-text">{appointment.shared_notes}</p></div>}
  </>;
}

export function AppointmentPrescriptionDownload({ appointmentId }: { appointmentId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);

  async function download() {
    if (pending.current) return;
    const request = new AbortController();
    pending.current = request;
    setBusy(true); setError('');
    try {
      const blob = await downloadMyPrescription(appointmentId, request.signal);
      if (request.signal.aborted) return;
      const extension = { 'application/pdf': '.pdf', 'image/jpeg': '.jpg', 'image/png': '.png' }[blob.type] ?? '';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `receta${extension}`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) {
      if (!request.signal.aborted) setError(consultationError(reason));
    } finally {
      pending.current = null;
      if (!request.signal.aborted) setBusy(false);
    }
  }

  return <div><button className="button secondary" type="button" disabled={busy} onClick={() => { void download(); }}>
    {busy ? 'Descargando…' : 'Descargar receta'}
  </button>{error && <p className="error-state" role="alert">{error}</p>}</div>;
}

export function PatientAppointmentDetailPage() {
  const { appointmentId = '' } = useParams();
  const load = useCallback((signal: AbortSignal) => getPatientFollowUp(appointmentId, signal), [appointmentId]);
  const state = useAdminQuery(load, consultationError);
  const appointment = state.data?.appointment_id === appointmentId ? state.data : null;
  return <main id="contenido" className="consultation-main consultation-patient">
    <header className="consultation-heading"><h1>Detalles de la cita</h1><Link className="button secondary" to="/patientPanel/misCitas">Volver a mis citas</Link></header>
    <PatientQueryFeedback {...state} />
    {appointment && <section className="consultation-info appointment-follow-up">
      <div><h2>{appointment.professional_name}</h2><p>{appointmentDate(appointment.start_time)}</p>
        {appointment.appointment_reason && <p>{appointment.appointment_reason}</p>}</div>
      <SharedAppointmentNotes appointment={appointment} />
      {appointment.has_prescription && <AppointmentPrescriptionDownload key={appointmentId} appointmentId={appointmentId} />}
      {!appointment.shared_diagnosis && !appointment.shared_notes && !appointment.has_prescription &&
        <p>El profesional todavía no ha compartido información sobre esta cita.</p>}
    </section>}
  </main>;
}
