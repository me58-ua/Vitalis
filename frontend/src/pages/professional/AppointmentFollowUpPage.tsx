import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getProfessionalFollowUp, saveFollowUpNotes, type ProfessionalFollowUp } from '../../api/appointmentFollowUp';
import { consultationError } from '../../api/consultations';
import { useAuth } from '../../auth/AuthContext';
import { appointmentDate } from '../../components/AppointmentSummary';
import { PrescriptionAttachment } from '../../components/PrescriptionAttachment';
import { PatientQueryFeedback } from '../../components/PatientDashboardDialogs';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import '../../styles/my-patients.css';

export function AppointmentFollowUpPage() {
  const { appointmentId = '' } = useParams();
  const { user } = useAuth();
  const load = useCallback((signal: AbortSignal) => getProfessionalFollowUp(appointmentId, signal), [appointmentId]);
  const state = useAdminQuery(load, consultationError);
  const appointment = state.data?.id === appointmentId ? state.data : null;
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, [appointmentId]);

  return <main id="contenido" className="professional-main consultation-main">
    <header className="consultation-heading"><div><h1 tabIndex={-1} ref={heading}>Seguimiento de la cita</h1>
      {appointment && <p>{appointment.patient_name} · {appointmentDate(appointment.start_time)}</p>}</div>
      <Link className="button secondary" to="/professionalDashboard/agenda">Volver a la agenda</Link>
    </header>
    <PatientQueryFeedback {...state} />
    {user && appointment && <FollowUpForm key={appointment.id} appointment={appointment} professionalId={user.id} />}
  </main>;
}

function FollowUpForm({ appointment, professionalId }: { appointment: ProfessionalFollowUp; professionalId: string }) {
  const [saving, setSaving] = useState(false);
  const [prescriptionOpen, setPrescriptionOpen] = useState(false);
  const [prescriptionBusy, setPrescriptionBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const data = new FormData(event.currentTarget);
    const value = (field: string) => String(data.get(field) ?? '').trim() || null;
    const request = new AbortController();
    pending.current = request;
    setSaving(true); setError(''); setMessage('');
    try {
      await saveFollowUpNotes(appointment.id, {
        shared_diagnosis: value('shared_diagnosis'),
        shared_notes: value('shared_notes'),
        clinical_notes: value('clinical_notes'),
      }, request.signal);
      if (!request.signal.aborted) setMessage('Seguimiento guardado.');
    } catch (reason) {
      if (!request.signal.aborted) setError(consultationError(reason));
    } finally {
      pending.current = null;
      if (!request.signal.aborted) setSaving(false);
    }
  }

  return <div className="appointment-follow-up">
    <section className="prescription-form" aria-labelledby="follow-up-notes">
      <h2 id="follow-up-notes">Diagnóstico y notas</h2>
      {!appointment.can_edit_notes && <p>Ha finalizado el plazo de edición de las notas.</p>}
      <form onSubmit={event => { void save(event); }}>
        <fieldset disabled={!appointment.can_edit_notes || saving}>
          <label>Diagnóstico compartido con el paciente<textarea name="shared_diagnosis" maxLength={2000} rows={3} defaultValue={appointment.shared_diagnosis ?? ''} /></label>
          <label>Notas clínicas para el paciente<textarea name="shared_notes" maxLength={10000} rows={4} defaultValue={appointment.shared_notes ?? ''} /></label>
          <label>Notas clínicas privadas<textarea name="clinical_notes" aria-describedby="private-notes-help" rows={4} defaultValue={appointment.clinical_notes ?? ''} /></label>
          <p id="private-notes-help" className="field-help">Solo tú puedes ver estas notas en el historial del paciente.</p>
          {appointment.can_edit_notes && <button className="button primary" type="submit">{saving ? 'Guardando…' : 'Guardar seguimiento'}</button>}
        </fieldset>
      </form>
      {message && <p role="status" className="success-state">{message}</p>}
      {error && <p role="alert" className="error-state">{error}</p>}
    </section>
    {prescriptionOpen ? <PrescriptionAttachment professionalId={professionalId} appointment={appointment}
      onBusy={setPrescriptionBusy} onCancel={() => { if (!prescriptionBusy) setPrescriptionOpen(false); }} />
      : <section className="prescription-form"><h2>Receta</h2><button className="button secondary" type="button"
        onClick={() => setPrescriptionOpen(true)}>Vincular receta</button></section>}
  </div>;
}
