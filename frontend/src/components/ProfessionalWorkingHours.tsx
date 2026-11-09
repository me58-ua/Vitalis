import { useEffect, useRef, useState, type FormEvent } from 'react';
import { getWorkingHours, saveWorkingHoursBatch, deleteWorkingHoursBatch } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAdminQuery } from '../hooks/useAdminQuery';
import type { WorkingHours, WorkingHoursBatch } from '../types/api';
import { DateTimeField } from './DateTimeField';
import { groupWorkingHours, workingDays as days, type WorkingHoursGroup } from '../utils/workingHours';


export function ProfessionalWorkingHours({ onBusy, onChanged }: { onBusy: (busy: boolean) => void; onChanged: () => void }) {
  const state = useAdminQuery(getWorkingHours, professionalError);
  const [channel, setChannel] = useState<WorkingHours['channel']>('consultation');
  const [editing, setEditing] = useState<WorkingHoursGroup | 'new' | null>(null);
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
    const selectedDays = form.getAll('hours_days').map(Number);
    if (selectedDays.length === 0) { setError('Selecciona al menos un día de la semana.'); return; }
    const minutes = (value: string) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
    if (end <= start || (channel === 'consultation' && duration > minutes(end) - minutes(start))) { setError('El fin debe ser posterior al inicio y debe caber al menos una cita completa. Para pasar de medianoche, usa franjas de días distintos.'); return; }
    const payload: WorkingHoursBatch = { channel, days_of_week: selectedDays, schedule_ids: editing && editing !== 'new' ? editing.rows.map(row => row.id) : [], start_time: start, end_time: end, slot_duration_min: duration, is_active: form.has('hours_active') };
    void mutate(signal => saveWorkingHoursBatch(payload, signal), 'Horario guardado para todos los días seleccionados. Las citas existentes se conservan.');
  }
  const group = editing && editing !== 'new' ? editing : null;
  const row = group?.row;
  const groups = groupWorkingHours(state.data?.filter(item => item.channel === channel) ?? []);
  function toggle(group: WorkingHoursGroup) {
    const first = group.row;
    void mutate(signal => saveWorkingHoursBatch({ channel, days_of_week: group.rows.map(item => item.day_of_week), schedule_ids: group.rows.map(item => item.id), start_time: first.start_time, end_time: first.end_time, slot_duration_min: first.slot_duration_min, is_active: !first.is_active }, signal), first.is_active ? 'Franjas desactivadas.' : 'Franjas activadas.');
  }
  return <details className="agenda-working-hours"><summary>Configurar horarios de citas y chat</summary>
    <h2>Horario semanal de atención</h2><p>Horas de Madrid. Configura por separado citas/videoconsultas y chat sin cita. Puedes añadir varios tramos por día. Un día sin franjas activas queda cerrado para ese canal.</p>
    <div className="working-hours-tabs" role="group" aria-label="Canal de atención"><button className="button secondary" type="button" disabled={busy} aria-pressed={channel === 'consultation'} onClick={() => { setChannel('consultation'); setEditing(null); setDeleting(null); setError(''); }}>Citas y videoconsultas</button><button className="button secondary" type="button" disabled={busy} aria-pressed={channel === 'chat'} onClick={() => { setChannel('chat'); setEditing(null); setDeleting(null); setError(''); }}>Chat espontáneo</button></div>
    {channel === 'chat' && <p>El paciente puede iniciar un chat sin reservar cita. No se añade a «Mis pacientes». Fuera de este horario, durante bloqueos o mientras tienes una cita en curso, los chats quedan en solo lectura.</p>}
    {state.loading && <p role="status">Cargando horarios…</p>}{state.error && <div className="error-state" role="alert"><p>{state.error}</p><button onClick={state.retry}>Reintentar horarios</button></div>}
    {notice && <p className="success-state" role="status">{notice}</p>}{error && <p className="error-state" role="alert">{error}</p>}
    <button className="button primary" disabled={busy || !state.data} onClick={() => { setEditing('new'); setError(''); }}>Añadir franja</button>
    {editing && <form key={group?.key ?? `new-${channel}`} className="form-grid working-hours-form" aria-busy={busy} onSubmit={submit}><fieldset className="form-grid full" disabled={busy}>
      <fieldset className="working-day-picker full"><legend>Días de la semana *</legend>{days.map((day, index) => <label className="checkbox" key={day}><input type="checkbox" name="hours_days" value={index} defaultChecked={group ? group.rows.some(item => item.day_of_week === index) : index === 0} />{day}</label>)}</fieldset>
      {group && <p className="field-help full">Los cambios se aplicarán juntos a los días seleccionados. Si desmarcas un día del grupo, se eliminará esa franja de ese día.</p>}
      <label>Desde *<DateTimeField type="time" name="hours_start" required step={60} defaultValue={row?.start_time.slice(0, 5) ?? '09:00'} /></label>
      <label>Hasta *<DateTimeField type="time" name="hours_end" required step={60} defaultValue={row?.end_time.slice(0, 5) ?? '13:00'} /></label>
      {channel === 'consultation' && <label>Duración de cada cita (minutos) *<input type="number" name="hours_duration" required min={1} max={1440} step={1} defaultValue={row?.slot_duration_min ?? 30} /></label>}
      <label className="checkbox full"><input type="checkbox" name="hours_active" defaultChecked={row?.is_active ?? true} />Franja activa</label>
      <button className="button primary" type="submit">{busy ? 'Guardando…' : 'Guardar horario'}</button><button className="button secondary" type="button" onClick={() => setEditing(null)}>Cancelar edición</button>
    </fieldset></form>}
    {state.data && <ul className="working-hours-list">{groups.map(group => { const item = group.row; return <li key={group.key}><strong>{group.label} · {item.start_time.slice(0, 5)}–{item.end_time.slice(0, 5)}</strong><p>{item.is_active ? 'Activa' : 'Desactivada'}{channel === 'consultation' && ` · Citas de ${item.slot_duration_min} minutos`}</p>
      {deleting === group.key ? <><p>¿Eliminar esta franja de {group.label}? Las citas ya reservadas se conservan.</p><button className="button secondary" disabled={busy} onClick={() => { void mutate(signal => deleteWorkingHoursBatch(group.rows.map(item => item.id), signal), 'Franjas eliminadas.'); }}>Confirmar eliminación</button><button className="text-button" disabled={busy} onClick={() => setDeleting(null)}>Conservar franja</button></> : <div className="working-hours-actions"><button className="text-button" disabled={busy} onClick={() => { setEditing(group); setError(''); }}>Editar franja</button><button className="text-button" disabled={busy} onClick={() => toggle(group)}>{item.is_active ? 'Desactivar' : 'Activar'}</button><button className="text-button" disabled={busy} onClick={() => setDeleting(group.key)}>Eliminar franja</button></div>}
    </li>; })}</ul>}
    {state.data?.filter(item => item.channel === channel && item.is_active).length === 0 && <p>No hay franjas activas para este canal. No se admiten nuevas consultas en él hasta que actives alguna.</p>}
  </details>;
}
