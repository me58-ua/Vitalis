import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { attachPrescription, getPatientHistory, getPatientPrescriptions, getPatientSnapshot } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAuth } from '../auth/AuthContext';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { Modal } from './Modal';
import { appointmentDate, appointmentStatuses, appointmentTypes } from './AppointmentSummary';
import { PatientPages } from './PatientPages';
import type { ProfessionalHistoryPage, ProfessionalPatientPage } from '../types/api';

function recordError(error: unknown) {
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    if (error.response?.data.detail === 'NO_SHARED_APPOINTMENT') return 'El resumen de salud requiere una cita compartida con este paciente.';
    if (error.response?.status === 403) return 'No se puede adjuntar la receta. Comprueba los permisos y el plazo de emisión; fuera de plazo se requiere autorización administrativa.';
    if (error.response?.status === 409) return 'Los datos han cambiado o no se pudo guardar la receta. Actualiza el expediente e inténtalo de nuevo.';
    if (error.response?.status === 422) return 'Comprueba que la cita esté finalizada y que el archivo sea PDF, JPEG o PNG, dentro del tamaño permitido por el servidor.';
  }
  return professionalError(error);
}
function Feedback({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  return <>{loading && <p role="status">Cargando…</p>}{error && <div className="error-state" role="alert"><p>{error}</p><button type="button" onClick={retry}>Reintentar</button></div>}</>;
}

export function PatientRecord({ patient, onClose }: { patient: ProfessionalPatientPage['patients'][number]; onClose: () => void }) {
  const { user } = useAuth();
  const professionalId = user?.id ?? '';
  const [page, setPage] = useState(1);
  const [recipePage, setRecipePage] = useState(1);
  const [appointment, setAppointment] = useState<ProfessionalHistoryPage['appointments'][number] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const lock = useRef(false);
  const upload = useRef<AbortController | null>(null);
  const historyLoad = useCallback((signal: AbortSignal) => getPatientHistory(professionalId, patient.id, page, signal), [professionalId, patient.id, page]);
  const recipeLoad = useCallback((signal: AbortSignal) => getPatientPrescriptions(professionalId, patient.id, recipePage, signal), [professionalId, patient.id, recipePage]);
  const healthLoad = useCallback((signal: AbortSignal) => getPatientSnapshot(patient.id, signal), [patient.id]);
  const history = useAdminQuery(historyLoad, professionalError);
  const recipes = useAdminQuery(recipeLoad, professionalError);
  const health = useAdminQuery(healthLoad, recordError);
  useEffect(() => () => upload.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || !appointment || appointment.patient_id !== patient.id || appointment.status !== 'completed') return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get('file');
    if (!(file instanceof File) || file.size === 0) { setError('Selecciona un archivo con contenido.'); return; }
    if (!['application/pdf', 'image/jpeg', 'image/png'].includes(file.type)) { setError('Selecciona un archivo PDF, JPEG o PNG.'); return; }
    lock.current = true; setBusy(true); setError(''); setSuccess('');
    const controller = new AbortController(); upload.current = controller;
    try {
      await attachPrescription(professionalId, appointment.id, file, String(data.get('notes') ?? ''), controller.signal);
      if (!controller.signal.aborted) { form.reset(); setAppointment(null); setSuccess('Receta guardada y vinculada a la cita.'); recipes.retry(); health.retry(); }
    } catch (reason: unknown) { if (!controller.signal.aborted) setError(recordError(reason)); }
    finally { if (!controller.signal.aborted) { lock.current = false; setBusy(false); } }
  }

  return <Modal title={`Expediente de ${patient.name}`} onClose={onClose} busy={busy}>
    <div className="patient-record"><p>@{patient.username} · {patient.email} · {patient.tel || 'Teléfono no indicado'}</p>
      {success && <p role="status" className="success-state">{success}</p>}
      <section><h3>Citas e historial con este profesional</h3><p>Selecciona una cita finalizada para vincular su receta. Las citas más recientes aparecen primero. El servidor comprueba el plazo de emisión y los permisos.</p>
        <Feedback {...history} />
        {history.data && <>{history.data.appointments.length === 0 && <p>No hay citas pasadas con este paciente. No puedes adjuntar una receta sin una cita finalizada.</p>}
          <ul className="record-list">{[...history.data.appointments].sort((a, b) => Date.parse(b.start_time) - Date.parse(a.start_time)).map(item => <li key={item.id}>
            <strong>{appointmentDate(item.start_time)}</strong><span>{appointmentTypes[item.type]} · {appointmentStatuses[item.status]}</span>
            <span>Motivo: {item.appointment_reason || 'No indicado'}</span>
            {item.diagnosis && <p>Diagnóstico: {item.diagnosis}</p>}{item.clinical_notes && <p>Notas: {item.clinical_notes}</p>}{item.patient_summary && <p>Resumen: {item.patient_summary}</p>}
            {item.status === 'completed' && <button className="button secondary" disabled={busy} aria-pressed={appointment?.id === item.id} onClick={() => { setAppointment(item); setError(''); setSuccess(''); }}>Vincular receta a esta cita</button>}
          </li>)}</ul>
          <PatientPages page={history.data.page} size={history.data.page_size} total={history.data.total} onPage={setPage} />
        </>}
      </section>
      {appointment && <section className="prescription-form"><h3>Adjuntar receta</h3><p><strong>Cita vinculada: {appointmentDate(appointment.start_time)}</strong></p><p>{appointment.appointment_reason || 'Motivo no indicado'}</p><p>Si la cita ya tiene receta, este archivo la reemplazará. Fuera del plazo configurado se necesita autorización administrativa.</p>
        <form onSubmit={event => { void submit(event); }}><fieldset disabled={busy}><label>Archivo de receta (PDF, JPEG o PNG)<input name="file" type="file" accept="application/pdf,image/jpeg,image/png" required /></label><label>Notas opcionales<textarea name="notes" rows={3} /></label>
          {error && <p role="alert" className="error-state">{error}</p>}
          <div className="record-actions"><button className="button primary" type="submit">{busy ? 'Guardando…' : 'Guardar receta vinculada'}</button><button className="button secondary" type="button" onClick={() => { setAppointment(null); setError(''); }}>Cancelar</button></div>
        </fieldset></form>
      </section>}
      <section><h3>Recetas de este profesional</h3><Feedback {...recipes} />{recipes.data && <>{recipes.data.prescriptions.length === 0 && <p>No hay recetas para este paciente.</p>}<ul className="record-list">{recipes.data.prescriptions.map(item => <li key={item.id}><strong>Receta adjuntada el {appointmentDate(item.created_at)}</strong><small>Cita vinculada: {item.appointment_id}</small><p>{item.notas || 'Sin notas adicionales'}</p></li>)}</ul><PatientPages page={recipes.data.page} size={recipes.data.page_size} total={recipes.data.total} onPage={setRecipePage} /></>}</section>
      <section><h3>Resumen de salud compartido</h3><Feedback {...health} />{health.data && (!health.data.consent_shared ? <p>El paciente no comparte sus datos de salud.</p> : <dl className="record-health"><dt>Altura</dt><dd>{health.data.height_cm == null ? 'No indicada' : `${health.data.height_cm} cm`}</dd><dt>Peso</dt><dd>{health.data.weight_kg == null ? 'No indicado' : `${health.data.weight_kg} kg`}</dd><dt>Alergias registradas</dt><dd>{health.data.allergies.length ? health.data.allergies.map(item => item.name).join(', ') : 'Sin registros'}</dd><dt>Medicamentos registrados</dt><dd>{health.data.medications.length ? health.data.medications.map(item => `${item.name}: ${item.dosage}, ${item.frequency}`).join('; ') : 'Sin registros'}</dd></dl>)}</section>
    </div>
  </Modal>;
}
