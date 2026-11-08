import { useEffect, useRef, useState, type FormEvent } from 'react';
import { getWorkingHours, saveWorkingHours, deleteWorkingHours } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAdminQuery } from '../hooks/useAdminQuery';
import type { WorkingHours, WorkingHoursCreate } from '../types/api';

const days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

export function ProfessionalWorkingHours({ onBusy, onChanged }: { onBusy: (busy: boolean) => void; onChanged: () => void }) {
  const state = useAdminQuery(getWorkingHours, professionalError);
  const [channel, setChannel] = useState<WorkingHours['channel']>('consultation');
  const [editing, setEditing] = useState<WorkingHours | 'new' | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const controller = useRef<AbortController | null>(null);
  const locked = useRef(false);
  useEffect(() => () => controller.current?.abort(), []);
  async function mutate(operation: (signal: AbortSignal) => Promise<unknown>, message: string) {
    if (locked.current) return;
    locked.current = true; setBusy(true); onBusy(true); setError(''); setNotice('');
    const abort = new AbortController(); controller.current = abort;
    try { await operation(abort.signal); if (!abort.signal.aborted) { setNotice(message); setEditing(null); setDeleting(null); state.retry(); onChanged(); } }
    catch (error: unknown) { if (!abort.signal.aborted) setError(professionalError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const start = String(form.get('hours_start')), end = String(form.get('hours_end'));
    const duration = channel === 'consultation' ? Number(form.get('hours_duration')) : 30;
    const minutes = (value: string) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
    if (end <= start || (channel === 'consultation' && duration > minutes(end) - minutes(start))) { setError('El fin debe ser posterior al inicio y debe caber al menos una cita completa. Para pasar de medianoche, usa franjas de días distintos.'); return; }
    const payload: WorkingHoursCreate = { channel, day_of_week: Number(form.get('hours_day')), start_time: start, end_time: end, slot_duration_min: duration, is_active: form.has('hours_active') };
    void mutate(signal => saveWorkingHours(payload, editing && editing !== 'new' ? editing.id : null, signal), 'Horario guardado. Se aplica a nuevas reservas y al acceso al chat; las citas existentes se conservan.');
  }
  const row = editing && editing !== 'new' ? editing : null;
  return <details className="agenda-working-hours"><summary>Configurar horarios de citas y chat</summary>
    <h2>Horario semanal de atención</h2><p>Horas de Madrid. Configura por separado citas/videoconsultas y chat sin cita. Puedes añadir varios tramos por día. Un día sin franjas activas queda cerrado para ese canal.</p>
    <div className="working-hours-tabs" role="group" aria-label="Canal de atención"><button className="button secondary" type="button" disabled={busy} aria-pressed={channel === 'consultation'} onClick={() => { setChannel('consultation'); setEditing(null); setDeleting(null); setError(''); }}>Citas y videoconsultas</button><button className="button secondary" type="button" disabled={busy} aria-pressed={channel === 'chat'} onClick={() => { setChannel('chat'); setEditing(null); setDeleting(null); setError(''); }}>Chat espontáneo</button></div>
    {channel === 'chat' && <p>El paciente puede iniciar un chat sin reservar cita. No se añade a «Mis pacientes». Fuera de este horario, durante bloqueos o mientras tienes una cita en curso, los chats quedan en solo lectura.</p>}
    {state.loading && <p role="status">Cargando horarios…</p>}{state.error && <div className="error-state" role="alert"><p>{state.error}</p><button onClick={state.retry}>Reintentar horarios</button></div>}
    {notice && <p className="success-state" role="status">{notice}</p>}{error && <p className="error-state" role="alert">{error}</p>}
    <button className="button primary" disabled={busy || !state.data} onClick={() => { setEditing('new'); setError(''); }}>Añadir franja</button>
    {editing && <form key={row?.id ?? `new-${channel}`} className="form-grid working-hours-form" aria-busy={busy} onSubmit={submit}><fieldset className="form-grid full" disabled={busy}>
      <label>Día *<select name="hours_day" defaultValue={row?.day_of_week ?? 0}>{days.map((day, index) => <option value={index} key={day}>{day}</option>)}</select></label>
      <label>Desde *<input type="time" name="hours_start" required step={60} defaultValue={row?.start_time.slice(0, 5) ?? '09:00'} /></label>
      <label>Hasta *<input type="time" name="hours_end" required step={60} defaultValue={row?.end_time.slice(0, 5) ?? '13:00'} /></label>
      {channel === 'consultation' && <label>Duración de cada cita (minutos) *<input type="number" name="hours_duration" required min={1} max={1440} step={1} defaultValue={row?.slot_duration_min ?? 30} /></label>}
      <label className="checkbox full"><input type="checkbox" name="hours_active" defaultChecked={row?.is_active ?? true} />Franja activa</label>
      <button className="button primary" type="submit">{busy ? 'Guardando…' : 'Guardar horario'}</button><button className="button secondary" type="button" onClick={() => setEditing(null)}>Cancelar edición</button>
    </fieldset></form>}
    {state.data && <ul className="working-hours-list">{state.data.filter(item => item.channel === channel).map(item => <li key={item.id}><strong>{days[item.day_of_week]} · {item.start_time.slice(0, 5)}–{item.end_time.slice(0, 5)}</strong><p>{item.is_active ? 'Activa' : 'Desactivada'}{channel === 'consultation' && ` · Citas de ${item.slot_duration_min} minutos`}</p>
      {deleting === item.id ? <><p>¿Eliminar esta franja? Las citas ya reservadas se conservan.</p><button className="button secondary" disabled={busy} onClick={() => { void mutate(signal => deleteWorkingHours(item.id, signal), 'Franja eliminada.'); }}>Confirmar eliminación</button><button className="text-button" disabled={busy} onClick={() => setDeleting(null)}>Conservar franja</button></> : <div className="working-hours-actions"><button className="text-button" disabled={busy} onClick={() => { setEditing(item); setError(''); }}>Editar franja</button><button className="text-button" disabled={busy} onClick={() => { void mutate(signal => saveWorkingHours({ is_active: !item.is_active }, item.id, signal), item.is_active ? 'Franja desactivada.' : 'Franja activada.'); }}>{item.is_active ? 'Desactivar' : 'Activar'}</button><button className="text-button" disabled={busy} onClick={() => setDeleting(item.id)}>Eliminar franja</button></div>}
    </li>)}</ul>}
    {state.data?.filter(item => item.channel === channel && item.is_active).length === 0 && <p>No hay franjas activas para este canal. No se admiten nuevas consultas en él hasta que actives alguna.</p>}
  </details>;
}
