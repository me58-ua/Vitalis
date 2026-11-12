import { useEffect, useRef, useState, type FormEvent } from 'react';
import { availabilityLabels, closeSpontaneousChat, getSpontaneousFile, sendSpontaneousMessage, spontaneousChatError } from '../api/spontaneousChat';
import { useSpontaneousRoom } from '../hooks/useSpontaneousRoom';
import { useSpontaneousRealtime } from '../hooks/useSpontaneousRealtime';
import { UserAvatar } from './UserAvatar';
import { appointmentDate } from './AppointmentSummary';
import type { SpontaneousMessage, User } from '../types/api';

function Attachment({ message }: { message: SpontaneousMessage }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [preview, setPreview] = useState('');
  const controller = useRef<AbortController | null>(null), url = useRef('');
  const locked = useRef(false);
  useEffect(() => () => { controller.current?.abort(); if (url.current) URL.revokeObjectURL(url.current); }, []);
  async function load(show: boolean) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(''); const abort = new AbortController(); controller.current = abort;
    try {
      const blob = await getSpontaneousFile(message.chat_id, message.id, abort.signal);
      if (abort.signal.aborted) return;
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = URL.createObjectURL(blob);
      if (show) setPreview(url.current);
      else { setPreview(''); const anchor = document.createElement('a'); anchor.href = url.current; anchor.download = message.file_name || 'adjunto'; anchor.click(); }
    } catch (error: unknown) { if (!abort.signal.aborted) setError(spontaneousChatError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  return <div className="spontaneous-attachment"><p>Adjunto: {message.file_name} ({Math.ceil((message.file_size ?? 0) / 1024)} KiB)</p><button className="text-button" disabled={busy} onClick={() => { void load(false); }}>Descargar adjunto</button>{message.content_type?.startsWith('image/') && <button className="text-button" disabled={busy} onClick={() => { if (preview) setPreview(''); else void load(true); }}>{preview ? 'Ocultar imagen' : 'Ver imagen'}</button>}{preview && <img src={preview} alt={message.file_name || 'Imagen adjunta'} />}{error && <p className="error-state" role="alert">{error}</p>}</div>;
}

export function SpontaneousChatRoom({ id, user, onChanged }: { id: string; user: User; onChanged: () => void }) {
  const chat = useSpontaneousRoom(id);
  const realtime = useSpontaneousRealtime(id, user.id, chat.retry);
  const [draft, setDraft] = useState(''), [file, setFile] = useState<File | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState(''), [closing, setClosing] = useState(false);
  const locked = useRef(false), requestId = useRef<string | null>(null), controller = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const lastMessageId = chat.messages.at(-1)?.id;
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'nearest' }); }, [lastMessageId]);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (locked.current || !chat.room?.can_write) return;
    if (file && (file.size === 0 || file.size > 10 * 1024 * 1024 || !['application/pdf', 'image/jpeg', 'image/png'].includes(file.type))) { setError('Adjunta PDF, JPEG o PNG no vacío de hasta 10 MiB.'); return; }
    realtime.notifyTyping(false);
    locked.current = true; setBusy(true); setError(''); requestId.current ??= crypto.randomUUID();
    const abort = new AbortController(); controller.current = abort;
    try { const message = await sendSpontaneousMessage(id, requestId.current, draft, file, abort.signal); if (!abort.signal.aborted) { chat.add(message); setDraft(''); setFile(null); if (fileInput.current) fileInput.current.value = ''; requestId.current = null; onChanged(); } }
    catch (error: unknown) { if (!abort.signal.aborted) { setError(spontaneousChatError(error)); chat.retry(); } }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  async function close() {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(''); const abort = new AbortController(); controller.current = abort;
    try { const room = await closeSpontaneousChat(id, abort.signal); if (!abort.signal.aborted) { chat.setRoom(room); setClosing(false); onChanged(); } }
    catch (error: unknown) { if (!abort.signal.aborted) setError(spontaneousChatError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  return <section className="spontaneous-room" aria-label="Conversación sin cita"><header>{chat.room && <UserAvatar name={user.role === 'patient' ? chat.room.professional_name : chat.room.patient_name} photoUrl={user.role === 'patient' ? chat.room.professional_photo_url : chat.room.patient_photo_url} />}<h2>{chat.room ? user.role === 'patient' ? chat.room.professional_name : chat.room.patient_name : 'Conversación'}</h2><span role="status">{realtime.connected ? 'Conectado' : 'Reconectando · actualización periódica'}</span>{chat.room && <p role="status">{chat.room.status === 'closed' ? 'Conversación cerrada' : availabilityLabels[chat.room.availability.reason]}</p>}</header>
    {chat.loading && <p role="status">Cargando conversación…</p>}{(chat.error || error) && <div className="error-state" role="alert"><p>{error || chat.error}</p><button className="text-button" disabled={busy} onClick={() => { setError(''); chat.retry(); }}>Actualizar conversación</button></div>}
    {chat.room && !chat.room.can_write && <p className="chat-readonly">Solo lectura. {chat.room.status === 'closed' ? 'La conversación ha terminado.' : 'Se podrá escribir cuando el médico vuelva a estar disponible en su horario de chat.'}</p>}
    <div className="spontaneous-messages" role="log" aria-label="Mensajes de la conversación" aria-live="polite" aria-relevant="additions">
      {chat.hasOlder && <button className="text-button" disabled={chat.olderBusy} onClick={() => { void chat.loadOlder(); }}>Mensajes anteriores</button>}
      {!chat.loading && chat.messages.length === 0 && !chat.error && <p>Todavía no hay mensajes. Escribe o adjunta un archivo para consultar al médico.</p>}
      {chat.messages.map(message => <article key={message.id} className={`spontaneous-message${message.sender_id === user.id ? ' is-own' : ''}`}><p>{message.content}</p>{message.file_name && <Attachment message={message} />}<footer>{message.sender_id === user.id ? 'Tú' : user.role === 'patient' ? chat.room?.professional_name : chat.room?.patient_name} · {appointmentDate(message.created_at)}</footer></article>)}
      <div ref={bottom} />
    </div>
    <p className="chat-typing" role="status">{realtime.typing && chat.room?.can_write ? 'Escribiendo…' : ''}</p>
    <form className="spontaneous-compose" onSubmit={event => { void submit(event); }}><fieldset disabled={busy || !chat.room?.can_write || Boolean(chat.error)}><label>Mensaje<textarea name="spontaneous_message" rows={3} maxLength={2000} value={draft} onBlur={() => realtime.notifyTyping(false)} onChange={event => { setDraft(event.target.value); realtime.notifyTyping(Boolean(event.target.value.trim())); requestId.current = null; }} /></label><label>Archivo o imagen (opcional)<input ref={fileInput} name="spontaneous_file" type="file" accept="application/pdf,image/jpeg,image/png" onChange={event => { setFile(event.target.files?.[0] ?? null); requestId.current = null; }} /></label><p className="field-help">PDF, JPEG o PNG, hasta 10 MiB. Solo los dos participantes pueden descargarlo.</p><button type="submit" className="button primary" disabled={!draft.trim() && !file}>{busy ? 'Enviando…' : 'Enviar mensaje'}</button></fieldset></form>
    {chat.room?.status === 'open' && <div className="spontaneous-close">{closing ? <><p>¿Cerrar esta conversación? El historial seguirá disponible y no se podrán enviar más mensajes.</p><button className="button secondary" disabled={busy} onClick={() => { void close(); }}>Confirmar cierre</button><button className="text-button" disabled={busy} onClick={() => setClosing(false)}>Volver</button></> : <button className="button secondary" disabled={busy} onClick={() => setClosing(true)}>Cerrar conversación</button>}</div>}
  </section>;
}
