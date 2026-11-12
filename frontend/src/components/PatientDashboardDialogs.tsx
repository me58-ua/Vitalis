import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Modal } from './Modal';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { getPatientHabits, getPatientRiskHistory, uploadPatientDocument, patientUploadError } from '../api/patient';
import { riskNames, riskValue, trendNames } from './PatientRiskCards';
import type { PatientProfile, User } from '../types/api';
import type { DocumentType } from '../api/documents';

export function patientDate(value: string, timezone = 'Europe/Madrid') {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Fecha no disponible';
  try { return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: timezone }).format(date); }
  catch { return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' }).format(date); }
}
export function PatientQueryFeedback({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  return <>{loading && <p role="status">Cargando…</p>}{error && <div className="error-state" role="alert"><p>{error}</p><button className="button secondary" onClick={retry}>Reintentar</button></div>}</>;
}
export function PatientHistoryDialog({ profile, initialModel, onClose }: { profile: PatientProfile; initialModel: string; onClose: () => void }) {
  const [model, setModel] = useState(initialModel);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const cursor = cursors.at(-1) ?? null;
  const load = useCallback((signal: AbortSignal) => getPatientRiskHistory(profile.id, model, cursor, signal), [profile.id, model, cursor]);
  const state = useAdminQuery(load);
  return <Modal title="Historial de evaluaciones" onClose={onClose}><div className="patient-dialog-content">
    <label>Evaluación<select value={model} onChange={event => { setModel(event.target.value); setCursors([null]); }}><option value="">Todas las evaluaciones</option>{Object.entries(riskNames).map(([key, name]) => <option value={key} key={key}>{name}</option>)}</select></label>
    <PatientQueryFeedback {...state} />
    {state.data && (state.data.ai_consent_required ? <p>Necesitas activar el consentimiento de evaluación para consultar el historial.</p> : <>
      {model && <p>Tendencia: {trendNames[state.data.trend] ?? 'No disponible'}</p>}
      <p className="field-help">Estos son registros guardados. El resumen actual puede contener cálculos más recientes.</p>
      {!state.data.snapshots.length ? <p>No hay evaluaciones guardadas para esta selección.</p> : <ul className="patient-record-list">{state.data.snapshots.map(item => <li key={item.id}><strong>{riskNames[item.model] ?? 'Evaluación adicional'}</strong><span>{riskValue(item.model, item.metric_value)}</span><time dateTime={item.computed_at}>{patientDate(item.computed_at, profile.timezone)}</time></li>)}</ul>}
      <nav className="pagination" aria-label="Páginas del historial"><button disabled={cursors.length === 1} onClick={() => setCursors(previous => previous.slice(0, -1))}>Anterior</button><span>Página {cursors.length}</span><button disabled={!state.data.next_cursor} onClick={() => { const next = state.data?.next_cursor; if (next) setCursors(previous => [...previous, next]); }}>Siguiente</button></nav>
    </>)}
  </div></Modal>;
}
export function PatientHabitsDialog({ onClose }: { onClose: () => void }) {
  const [page, setPage] = useState(1);
  const load = useCallback((signal: AbortSignal) => getPatientHabits(page, signal), [page]);
  const state = useAdminQuery(load);
  const names: Record<string, string> = { sueno: 'Sueño', ejercicio: 'Ejercicio', dieta: 'Alimentación', tabaco: 'Tabaco' };
  return <Modal title="Tus hábitos registrados" onClose={onClose}><div className="patient-dialog-content"><PatientQueryFeedback {...state} />
    {state.data && <>{!state.data.habits.length ? <p>No hay hábitos registrados.</p> : <ul className="patient-record-list">{state.data.habits.map(item => <li key={item.id}><strong>{names[item.habit_type] ?? 'Hábito'}</strong><span>{item.value == null ? 'Sin valor numérico' : new Intl.NumberFormat('es-ES').format(item.value)} {item.unit}</span><time dateTime={item.date}>{item.date.split('-').reverse().join('/')}</time></li>)}</ul>}
      <nav className="pagination" aria-label="Páginas de hábitos"><button disabled={page === 1} onClick={() => setPage(value => value - 1)}>Anterior</button><span>Página {page}</span><button disabled={page * state.data.page_size >= state.data.total} onClick={() => setPage(value => value + 1)}>Siguiente</button></nav></>}
  </div></Modal>;
}
export function PatientProfileDialog({ user, profile, onClose }: { user: User; profile: PatientProfile; onClose: () => void }) {
  return <Modal title="Tu perfil" onClose={onClose}><dl className="patient-profile-details"><dt>Nombre</dt><dd>{user.name}</dd><dt>Correo electrónico</dt><dd>{user.email}</dd><dt>Altura</dt><dd>{profile.height_cm == null ? 'Sin registrar' : `${profile.height_cm} cm`}</dd><dt>Peso</dt><dd>{profile.weight_kg == null ? 'Sin registrar' : `${profile.weight_kg} kg`}</dd><dt>Grupo sanguíneo</dt><dd>{profile.blood_type || 'Sin registrar'}</dd><dt>Zona horaria</dt><dd>{profile.timezone}</dd></dl></Modal>;
}
export function PatientUploadDialog({ onClose }: { onClose: () => void }) {
  const [tipo, setTipo] = useState<DocumentType>('informe');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const flight = useRef<AbortController | null>(null);
  useEffect(() => () => flight.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (flight.current || !file) return;
    const controller = new AbortController(); flight.current = controller; setBusy(true); setError('');
    try { await uploadPatientDocument(file, tipo, description, controller.signal); if (!controller.signal.aborted) setSuccess(true); }
    catch (failure: unknown) { if (!controller.signal.aborted) setError(patientUploadError(failure)); }
    finally { if (!controller.signal.aborted) { flight.current = null; setBusy(false); } }
  }
  return <Modal title="Subir documento de salud" onClose={onClose} busy={busy}>{success ? <div className="patient-dialog-content"><p role="status">Documento subido correctamente. Puedes encontrarlo en la búsqueda de documentos.</p><button className="button primary" onClick={onClose}>Cerrar</button></div> : <form className="patient-dialog-content" onSubmit={event => { void submit(event); }}>
    <label>Tipo de documento<select value={tipo} disabled={busy} onChange={event => { const value = event.target.value; if (value === 'informe' || value === 'analitica' || value === 'otro') setTipo(value); }}><option value="informe">Informe</option><option value="analitica">Analítica</option><option value="otro">Otro</option></select></label>
    <label>Archivo (PDF, JPEG o PNG)<input type="file" accept="application/pdf,image/jpeg,image/png" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
    <label>Descripción (opcional)<textarea value={description} disabled={busy} onChange={event => setDescription(event.target.value)} /></label>
    {error && <p className="error-state" role="alert">{error}</p>}<button className="button primary" type="submit" disabled={busy || !file}>{busy ? 'Subiendo…' : 'Subir documento'}</button>
  </form>}</Modal>;
}
