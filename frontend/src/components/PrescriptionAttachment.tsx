import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { attachPrescription, downloadProfessionalPrescription, getAppointmentPrescription } from '../api/professional';
import type { PrescriptionMetadata } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { appointmentDate } from './AppointmentSummary';
import { DateTimeField } from './DateTimeField';
import type { Prescription, ProfessionalAppointment } from '../types/api';
import '../styles/my-patients.css';

type LinkedAppointment = Pick<ProfessionalAppointment, 'id' | 'patient_id' | 'status' | 'start_time'> & {
  appointment_reason?: ProfessionalAppointment['appointment_reason'];
};

function uploadError(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 403) return 'No se puede adjuntar la receta. Comprueba los permisos y el plazo de emisión; fuera de plazo se requiere autorización administrativa.';
    if (error.response?.status === 409) return 'La receta ha cambiado o no se pudo guardar. Actualiza sus datos e inténtalo de nuevo.';
    if (error.response?.status === 422) return 'Revisa el título, el tipo y las fechas. La caducidad no puede ser anterior a la emisión. La cita debe estar finalizada y el archivo debe ser PDF, JPEG o PNG dentro del tamaño permitido.';
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
  const [late, setLate] = useState(false);
  const [requested, setRequested] = useState(false);
  const [saveRevision, setSaveRevision] = useState(0);
  const [success, setSuccess] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const reasonField = useRef<HTMLTextAreaElement>(null);
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
  useEffect(() => {
    if (late) reasonField.current?.focus();
  }, [late]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked.current || requested || appointment.status !== 'completed') return;
    const form = event.currentTarget;
    const data = new FormData(form), file = data.get('file');
    if (!(file instanceof File) || !file.size) { setError('Selecciona un archivo con contenido.'); return; }
    if (!['application/pdf', 'image/jpeg', 'image/png'].includes(file.type)) { setError('Selecciona un archivo PDF, JPEG o PNG.'); return; }
    const metadata: PrescriptionMetadata = {
      tipo: String(data.get('tipo')) as PrescriptionMetadata['tipo'],
      titulo: String(data.get('titulo') ?? '').trim(),
      fecha_emision: String(data.get('fecha_emision') ?? ''),
      fecha_caducidad: String(data.get('fecha_caducidad') ?? '') || null,
      codigo: String(data.get('codigo') ?? '').trim() || null,
    };
    if (!metadata.titulo || !metadata.fecha_emision) { setError('Indica el título y la fecha de emisión del documento.'); return; }
    if (metadata.fecha_caducidad && metadata.fecha_caducidad < metadata.fecha_emision) {
      setError('La fecha de caducidad no puede ser anterior a la fecha de emisión.'); return;
    }
    const lateReason = String(data.get('late_reason') ?? '').trim();
    if (late && !lateReason) { setError('Indica el motivo de la demora.'); return; }
    locked.current = true; setBusy(true); onBusy(true); setError(''); setSuccess('');
    const controller = new AbortController(); upload.current = controller;
    try {
      const result = await attachPrescription(professionalId, appointment.id, file, String(data.get('notes') ?? ''), metadata, controller.signal, lateReason);
      if (controller.signal.aborted) return;
      if (result) {
        setSaved(result); setSaveRevision(value => value + 1);
        setSuccess('Receta guardada y vinculada a esta cita. Ya puedes descargarla.');
        onSaved?.();
      } else {
        setRequested(true);
        setSuccess('Solicitud enviada. Recibirás una notificación cuando se autorice y la receta quede vinculada.');
      }
    } catch (reason: unknown) {
      if (controller.signal.aborted) return;
      if (axios.isAxiosError(reason) && reason.response?.data?.detail === 'PRESCRIPTION_WINDOW_EXPIRED') {
        setLate(true);
      } else if (late && axios.isAxiosError(reason) && reason.response?.status === 409) {
        const detail = reason.response.data?.detail;
        setError(typeof detail === 'string' ? detail : 'No se pudo enviar la solicitud. Inténtalo de nuevo.');
      } else {
        setError(uploadError(reason));
      }
    }
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
    {requested ? <button className="button secondary" type="button" onClick={onCancel}>Cerrar formulario</button> :
    <form key={`${prescription?.id ?? 'new'}:${saveRevision}`} aria-busy={busy} onSubmit={event => { void submit(event); }}><fieldset disabled={busy || existing.loading || Boolean(existing.error)}>
      <label>Tipo de documento<select name="tipo" required defaultValue={prescription?.tipo ?? 'medicacion'}><option value="medicacion">Receta de medicación</option><option value="prueba">Solicitud de prueba o procedimiento</option><option value="otro">Otro</option></select></label>
      <label>Medicamento(s) o título del documento<input name="titulo" required maxLength={300} defaultValue={prescription?.titulo ?? ''} placeholder="Ej.: Atorvastatina 20 mg y Metformina 850 mg" /></label>
      <p className="field-help">Indica los datos que figuran en el documento. Las dosis, la frecuencia y las instrucciones se consultarán en el archivo adjunto.</p>
      <label>Fecha de emisión<DateTimeField name="fecha_emision" type="date" required defaultValue={prescription?.fecha_emision ?? ''} /></label>
      <label>Válida hasta (opcional)<DateTimeField name="fecha_caducidad" type="date" defaultValue={prescription?.fecha_caducidad ?? ''} /></label>
      <p className="field-help">Deja la caducidad en blanco si no está especificada en el documento.</p>
      <label>Código del documento (opcional)<input name="codigo" maxLength={100} defaultValue={prescription?.codigo ?? ''} /></label>
      <label>Archivo de receta (PDF, JPEG o PNG)<input name="file" type="file" accept="application/pdf,image/jpeg,image/png" required /></label>
      <label>Notas opcionales<textarea name="notes" rows={3} defaultValue={prescription?.notas ?? ''} /></label>
      {late && <>
        <p role="status">El plazo de emisión ha vencido. Solicita autorización administrativa para vincular la receta a la cita.</p>
        <label>Motivo de la demora<textarea ref={reasonField} name="late_reason" rows={3} maxLength={1000} required aria-describedby="late-reason-help" /></label>
        <p id="late-reason-help" className="field-help">Explica la demora sin incluir información clínica ni datos del paciente.</p>
      </>}
      {error && <p className="error-state" role="alert">{error}</p>}
      <div className="record-actions"><button className="button primary" type="submit">{busy ? 'Enviando…' : late ? 'Solicitar autorización' : 'Guardar receta vinculada'}</button><button className="button secondary" type="button" onClick={onCancel}>Cerrar formulario</button></div>
    </fieldset></form>}
  </section>;
}
