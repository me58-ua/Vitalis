import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { professionalFollowUpPath } from '../api/appointmentFollowUp';
import { getPatientHistory, getPatientPrescriptions, getPatientSnapshot, getSharedPatientRisks } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAuth } from '../auth/AuthContext';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { Modal } from './Modal';
import { CompleteInPersonAppointment } from './CompleteInPersonAppointment';
import { appointmentDate, appointmentStatuses, appointmentTypes } from './AppointmentSummary';
import { PatientPages } from './PatientPages';
import { PrescriptionAttachment, PrescriptionDownloadButton } from './PrescriptionAttachment';
import type { PatientHealthSnapshot, ProfessionalHistoryPage, ProfessionalPatientPage } from '../types/api';
import { riskNames, riskValue } from './PatientRiskCards';
import { familyConditionNames } from '../utils/familyHistory';
import { downloadDocument } from '../api/documents';

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

function SharedRisks({ profileId }: { profileId: string }) {
  const load = useCallback((signal: AbortSignal) => getSharedPatientRisks(profileId, signal), [profileId]);
  const state = useAdminQuery(load, professionalError);
  return <div><h4>Evaluaciones de riesgo</h4><Feedback {...state} />
    {state.data && (state.data.results.length ? <ul>{state.data.results.map(item => <li key={item.model}>
      <strong>{riskNames[item.model] ?? item.model}</strong> · {riskValue(item.model, item.metric_value)}<p>{item.explanation}</p>
    </li>)}</ul> : <p>No hay evaluaciones disponibles.</p>)}
  </div>;
}

const habitNames: Record<string, string> = { tabaco: 'Tabaco', ejercicio: 'Actividad física', sueno: 'Sueño', dieta: 'Fruta y verdura' };

function SharedDocuments({ documents, patientId, professionalId }: {
  documents: NonNullable<PatientHealthSnapshot['health_documents']>;
  patientId: string;
  professionalId: string;
}) {
  const request = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => () => request.current?.abort(), []);
  async function download(id: string) {
    if (request.current) return;
    const abort = new AbortController();
    request.current = abort;
    setBusy(true);
    setError('');
    try {
      await downloadDocument({ id, patient_user_id: patientId }, 'professional', professionalId, abort.signal);
    } catch (failure: unknown) {
      if (!abort.signal.aborted) setError(professionalError(failure));
    } finally {
      request.current = null;
      if (!abort.signal.aborted) setBusy(false);
    }
  }
  return <><h4>Documentos de salud</h4>
    {error && <p role="alert">{error}</p>}
    {documents.length ? <ul>{documents.map(item => <li key={item.id}>
      {item.descripcion ?? item.tipo} · <button type="button" className="text-button" disabled={busy} onClick={() => { void download(item.id); }}>Descargar</button>
    </li>)}</ul> : <p>Sin documentos.</p>}
  </>;
}

function SharedHealthData({ data, patientId, professionalId }: { data: PatientHealthSnapshot; patientId: string; professionalId: string }) {
  if (!data.consent_shared || !data.sharing_scope || data.sharing_scope === 'none') return <p>El paciente no comparte sus datos de salud.</p>;
  const full = data.sharing_scope === 'full';
  return <>
    <p>{full ? 'Perfil completo' : 'Datos básicos'}</p>
    <dl className="record-health">
      <dt>Edad</dt><dd>{data.age == null ? 'Sin registrar' : `${data.age} años`}</dd>
      <dt>Género</dt><dd>{data.gender ?? 'Sin registrar'}</dd>
      <dt>Altura</dt><dd>{data.height_cm == null ? 'Sin registrar' : `${data.height_cm} cm`}</dd>
      <dt>Peso</dt><dd>{data.weight_kg == null ? 'Sin registrar' : `${data.weight_kg} kg`}</dd>
      {full && <>
        <dt>Sexo al nacer</dt><dd>{data.sex_at_birth ?? 'Sin registrar'}</dd>
        <dt>Grupo sanguíneo</dt><dd>{data.blood_type ?? 'Sin registrar'}</dd>
        <dt>Alergias</dt><dd>{data.allergies?.map(item => `${item.name} (${item.severity})`).join(', ') || 'Sin registros'}</dd>
        <dt>Condiciones crónicas</dt><dd>{data.chronic_conditions?.map(item => item.condition_name).join(', ') || 'Sin registros'}</dd>
        <dt>Medicación</dt><dd>{data.medications?.map(item => `${item.name}: ${item.dosage}, ${item.frequency}`).join('; ') || 'Sin registros'}</dd>
        <dt>Antecedentes familiares</dt><dd>{data.family_history_entries?.map(item => [
          item.relative_detail || item.relationship, familyConditionNames[item.condition_category] ?? item.condition_category, item.detail,
          item.age_at_diagnosis == null ? null : `diagnóstico a los ${item.age_at_diagnosis} años`, item.notes,
        ].filter(Boolean).join(' · ')).join('; ') || 'Sin registros'}</dd>
      </>}
    </dl>
    <h4>Hábitos registrados</h4>
    {data.habit_logs?.length ? <ul>{data.habit_logs.map(item => <li key={item.id}>
      {habitNames[item.habit_type] ?? item.habit_type} · {item.value == null ? 'Sin valor' : `${item.value} ${item.unit ?? ''}`} · {item.date.split('-').reverse().join('/')}
    </li>)}</ul> : <p>Sin registros.</p>}
    <h4>Consumo de alcohol</h4>
    {data.alcohol_logs?.length ? <ul>{data.alcohol_logs.map(item => <li key={item.id}>
      {item.date.split('-').reverse().join('/')} · {['Nunca', 'Mensualmente o menos', 'De 2 a 4 veces al mes', 'De 2 a 3 veces a la semana', '4 o más veces a la semana'][item.frequency ?? -1] ?? 'Frecuencia sin registrar'}
    </li>)}</ul> : <p>Sin registros.</p>}
    {full && <SharedDocuments documents={data.health_documents ?? []} patientId={patientId} professionalId={professionalId} />}
    {full && data.profile_id && <SharedRisks profileId={data.profile_id} />}
  </>;
}

export function PatientRecord({ patient, onClose }: { patient: ProfessionalPatientPage['patients'][number]; onClose: () => void }) {
  const { user } = useAuth();
  const professionalId = user?.id ?? '';
  const [page, setPage] = useState(1);
  const [recipePage, setRecipePage] = useState(1);
  const [appointment, setAppointment] = useState<ProfessionalHistoryPage['appointments'][number] | null>(null);
  const [busy, setBusy] = useState(false);
  const [prescriptionFocus, setPrescriptionFocus] = useState(0);
  const selectionButton = useRef<HTMLButtonElement | null>(null);
  const historyLoad = useCallback((signal: AbortSignal) => getPatientHistory(professionalId, patient.id, page, signal), [professionalId, patient.id, page]);
  const recipeLoad = useCallback((signal: AbortSignal) => getPatientPrescriptions(professionalId, patient.id, recipePage, signal), [professionalId, patient.id, recipePage]);
  const healthLoad = useCallback((signal: AbortSignal) => getPatientSnapshot(patient.id, signal), [patient.id]);
  const history = useAdminQuery(historyLoad, professionalError);
  const recipes = useAdminQuery(recipeLoad, professionalError);
  const health = useAdminQuery(healthLoad, recordError);
  return <Modal title={`Expediente de ${patient.name}`} onClose={onClose} busy={busy}>
    <div className="patient-record"><p>@{patient.username} · {patient.email} · {patient.tel || 'Teléfono no indicado'}</p>
      <section><h3>Citas e historial</h3><p>Una vez iniciada una cita presencial, puedes finalizarla y abrir su seguimiento. Desde el seguimiento puedes guardar el diagnóstico, las notas y la receta.</p>
        <Feedback {...history} />
        {history.data && <>{history.data.appointments.length === 0 && <p>No hay citas iniciadas ni finalizadas con este paciente.</p>}
          <ul className="record-list">{[...history.data.appointments].sort((a, b) => Date.parse(b.start_time) - Date.parse(a.start_time)).map(item => <li key={item.id}>
            <strong>{appointmentDate(item.start_time)}</strong><span>{appointmentTypes[item.type]} · {appointmentStatuses[item.status]}</span>
            <span>Motivo: {item.appointment_reason || 'No indicado'}</span>
            {item.diagnosis && <p>Diagnóstico: {item.diagnosis}</p>}{item.clinical_notes && <p>Notas: {item.clinical_notes}</p>}{item.patient_summary && <p>Resumen: {item.patient_summary}</p>}
            {item.type === 'in_person' && item.status === 'confirmed' && <CompleteInPersonAppointment appointmentId={item.id} professionalId={professionalId} busy={busy} onBusy={setBusy} />}
            {item.status === 'completed' && <Link className="button secondary" to={professionalFollowUpPath(item.id)}>Seguimiento de la cita</Link>}
            {item.status === 'completed' && <button className="button secondary" disabled={busy} aria-pressed={appointment?.id === item.id} onClick={event => { selectionButton.current = event.currentTarget; setAppointment(item); setPrescriptionFocus(value => value + 1); }}>Vincular receta a esta cita</button>}
          </li>)}</ul>
          <PatientPages page={history.data.page} size={history.data.page_size} total={history.data.total} onPage={setPage} />
        </>}
      </section>
      {appointment && <PrescriptionAttachment focusRequest={prescriptionFocus} key={appointment.id} professionalId={professionalId} appointment={appointment} onBusy={setBusy} onSaved={() => { recipes.retry(); health.retry(); }} onCancel={() => { setAppointment(null); selectionButton.current?.focus(); }} />}
      <section><h3>Recetas</h3><p>Solo puedes adjuntar una receta después de finalizar la cita con el paciente.</p><Feedback {...recipes} />{recipes.data && <>{recipes.data.prescriptions.length === 0 && <p>No hay recetas para este paciente.</p>}<ul className="record-list">{recipes.data.prescriptions.map(item => <li key={item.id}><strong>Receta adjuntada el {appointmentDate(item.created_at)}</strong><p>{item.notas || 'Sin notas adicionales'}</p><PrescriptionDownloadButton professionalId={professionalId} appointmentId={item.appointment_id} /></li>)}</ul><PatientPages page={recipes.data.page} size={recipes.data.page_size} total={recipes.data.total} onPage={setRecipePage} /></>}</section>
      <section><h3>Resumen de salud compartido</h3><Feedback {...health} />{health.data && <SharedHealthData data={health.data} patientId={patient.id} professionalId={professionalId} />}</section>
    </div>
  </Modal>;
}
