import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { attachPrescription, downloadProfessionalPrescription, getAppointmentPrescription } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { appointmentDate } from './AppointmentSummary';
import type { Prescription, ProfessionalAppointment } from '../types/api';
import '../styles/my-patients.css';

type LinkedAppointment = Pick<ProfessionalAppointment, 'id' | 'patient_id' | 'status' | 'start_time'> & {
  appointment_reason?: ProfessionalAppointment['appointment_reason'];
};

function uploadError(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 403) return 'No se puede adjuntar la receta. Comprueba los permisos y el plazo de emisión; fuera de plazo se requiere autorización administrativa.';
    if (error.response?.status === 409) return 'La receta ha cambiado o no se pudo guardar. Actualiza sus datos e inténtalo de nuevo.';
    if (error.response?.status === 422) return 'Comprueba que la cita esté finalizada y que el archivo sea PDF, JPEG o PNG, dentro del tamaño permitido por el servidor.';
  }
  return professionalError(error);
}

export function PrescriptionDownloadButton({ professionalId, appointmentId }: { professionalId: string; appointmentId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const locked = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function download() {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError('');
    const controller = new AbortController(); request.current = controller;
    try {
      const blob = await downloadProfessionalPrescription(professionalId, appointmentId, controller.signal);
      if (controller.signal.aborted) return;
      const suffix = blob.type === 'application/pdf' ? '.pdf' : blob.type === 'image/jpeg' ? '.jpg' : blob.type === 'image/png' ? '.png' : '';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = `receta${suffix}`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason: unknown) {
      if (!controller.signal.aborted) setError(axios.isAxiosError(reason) && reason.response?.status === 404 ? 'El archivo de la receta no está disponible.' : `No se pudo descargar la receta. ${professionalError(reason)}`);
    } finally { if (!controller.signal.aborted) { locked.current = false; setBusy(false); } }
  }
  return <div className="prescription-download"><button type="button" className="button secondary" disabled={busy} onClick={() => { void download(); }}>{busy ? 'Descargando…' : error ? 'Reintentar descarga' : 'Descargar receta'}</button>{error && <p className="error-state" role="alert">{error}</p>}</div>;
}

export function PrescriptionAttachment({ professionalId, appointment, onBusy, onSaved, onCancel, focusRequest = 0 }: {
  professionalId: string; appointment: LinkedAppointment; onBusy: (busy: boolean) => void;
  onSaved?: () => void; onCancel: () => void; focusRequest?: number;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState<Prescription | null>(null);
  const [success, setSuccess] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const upload = useRef<AbortController | null>(null);
  const locked = useRef(false);
  const load = useCallback((signal: AbortSignal) => getAppointmentPrescription(professionalId, appointment.patient_id, appointment.id, signal), [professionalId, appointment.patient_id, appointment.id]);
  const existing = useAdminQuery(load, professionalError);
  const prescription = saved ?? existing.data;
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    heading.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
  }, [focusRequest]);
  useEffect(() => () => upload.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current || appointment.status !== 'completed') return;
    const form = event.currentTarget;
    const data = new FormData(form), file = data.get('file');
    if (!(file instanceof File) || !file.size) { setError('Selecciona un archivo con contenido.'); return; }
    if (!['application/pdf', 'image/jpeg', 'image/png'].includes(file.type)) { setError('Selecciona un archivo PDF, JPEG o PNG.'); return; }
    locked.current = true; setBusy(true); onBusy(true); setError(''); setSuccess('');
    const controller = new AbortController(); upload.current = controller;
    try {
      const result = await attachPrescription(professionalId, appointment.id, file, String(data.get('notes') ?? ''), controller.signal);
      if (!controller.signal.aborted) { form.reset(); setSaved(result); setSuccess('Receta guardada y vinculada a esta cita. Ya puedes descargarla.'); onSaved?.(); }
    } catch (reason: unknown) { if (!controller.signal.aborted) setError(uploadError(reason)); }
    finally { if (!controller.signal.aborted) { locked.current = false; setBusy(false); onBusy(false); } }
  }

  return <section className="prescription-form" aria-label="Adjuntar receta">
    <h3 tabIndex={-1} ref={heading}>Adjuntar receta</h3>
    <p><strong>Cita vinculada: {appointmentDate(appointment.start_time)}</strong></p><p>{appointment.appointment_reason || 'Motivo no indicado'}</p>
    {success && <p className="success-state" role="status">{success}</p>}
    {existing.loading && <p role="status">Comprobando si esta cita tiene receta…</p>}
    {existing.error && <div className="error-state" role="alert"><p>{existing.error}</p><button type="button" onClick={existing.retry}>Reintentar</button></div>}
    {prescription && <div className="prescription-current"><p>Esta cita tiene una receta vinculada.</p><PrescriptionDownloadButton professionalId={professionalId} appointmentId={appointment.id} /></div>}
    <p>El archivo queda vinculado a esta cita y disponible para el paciente. Si ya existe una receta, se reemplazará. Fuera del plazo de emisión se necesita autorización administrativa.</p>
    <form aria-busy={busy} onSubmit={event => { void submit(event); }}><fieldset disabled={busy || existing.loading || Boolean(existing.error)}>
      <label>Archivo de receta (PDF, JPEG o PNG)<input name="file" type="file" accept="application/pdf,image/jpeg,image/png" required /></label>
      <label>Notas opcionales<textarea name="notes" rows={3} /></label>
      {error && <p className="error-state" role="alert">{error}</p>}
      <div className="record-actions"><button className="button primary" type="submit">{busy ? 'Guardando…' : 'Guardar receta vinculada'}</button><button className="button secondary" type="button" onClick={onCancel}>Cerrar formulario</button></div>
    </fieldset></form>
  </section>;
}
