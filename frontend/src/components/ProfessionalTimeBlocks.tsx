import { useEffect, useRef, useState, type FormEvent } from 'react';
import { createTimeBlock, deleteTimeBlock } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { DateTimeField } from './DateTimeField';
import { appointmentDate } from './AppointmentSummary';
import type { ProfessionalTimeBlock } from '../types/api';

export function ProfessionalTimeBlocks({ blocks, ready, onBusy, onChanged }: { blocks: ProfessionalTimeBlock[]; ready: boolean; onBusy: (busy: boolean) => void; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function mutate(operation: (signal: AbortSignal) => Promise<unknown>, message: string) {
    if (locked.current) return;
    locked.current = true; setBusy(true); onBusy(true); setError(''); setNotice('');
    const abort = new AbortController(); controller.current = abort;
    try { await operation(abort.signal); if (!abort.signal.aborted) { setNotice(message); setDeleting(null); setOpen(false); onChanged(); } }
    catch (error: unknown) { if (!abort.signal.aborted) setError(professionalError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const start = new Date(String(values.get('block_start') ?? '')), end = new Date(String(values.get('block_end') ?? ''));
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) { setError('Introduce un intervalo válido con fin posterior al inicio.'); return; }
    void mutate(signal => createTimeBlock({ start_time: start.toISOString(), end_time: end.toISOString(), reason: String(values.get('block_reason') ?? '').trim() || null }, signal), 'Horario bloqueado. Se mostrará en las semanas que corresponden al intervalo.');
  }
  return <section className="agenda-time-blocks" aria-label="Horarios no disponibles">
    <div className="agenda-block-heading"><h2>Horarios no disponibles</h2><button className="button secondary" disabled={busy || !ready} aria-expanded={open} onClick={() => { setOpen(value => !value); setError(''); }}>Bloquear horario</button></div>
    <p>Bloquea vacaciones o ausencias por fecha y hora. Los intervalos impiden nuevas citas; no cancelan citas existentes. Se muestran los bloqueos que coinciden con la semana seleccionada.</p>
    {open && <form className="form-grid" aria-busy={busy} onSubmit={submit}><fieldset className="form-grid full" disabled={busy || !ready}>
      <label>Inicio del bloqueo *<DateTimeField type="datetime-local" name="block_start" required /></label>
      <label>Fin del bloqueo *<DateTimeField type="datetime-local" name="block_end" required /></label>
      <label className="full">Motivo (opcional, privado)<input name="block_reason" maxLength={250} /></label>
      <p className="field-help full">Introduce horas en la zona de tu navegador ({Intl.DateTimeFormat().resolvedOptions().timeZone}). La agenda las muestra en Madrid. Para días completos, elige las 00:00 del primer día hasta las 00:00 del día siguiente al último.</p>
      <button className="button primary" type="submit">{busy ? 'Guardando…' : 'Guardar bloqueo'}</button><button className="button secondary" type="button" onClick={() => setOpen(false)}>Cancelar</button>
    </fieldset></form>}
    {notice && <p className="success-state" role="status">{notice}</p>}{error && <p className="error-state" role="alert">{error}</p>}
    {ready && blocks.length === 0 && <p>No hay bloqueos en esta semana.</p>}
    <ul className="agenda-block-list">{blocks.map(block => <li key={block.id}><strong>{block.reason || 'No disponible'}</strong><p>{appointmentDate(block.start_time)} — {appointmentDate(block.end_time)}</p>{deleting === block.id ? <><p>¿Eliminar este bloqueo y volver a permitir reservas según tus horarios?</p><button className="button secondary" disabled={busy} onClick={() => { void mutate(signal => deleteTimeBlock(block.id, signal), 'Bloqueo eliminado.'); }}>Confirmar eliminación</button><button className="text-button" disabled={busy} onClick={() => setDeleting(null)}>Conservar bloqueo</button></> : <button className="text-button" disabled={busy} onClick={() => setDeleting(block.id)}>Eliminar bloqueo</button>}</li>)}</ul>
  </section>;
}
