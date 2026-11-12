import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useConsultationChat } from '../hooks/useConsultationChat';
import { appointmentDate } from './AppointmentSummary';
import { UserAvatar } from './UserAvatar';
import '../styles/videoconsulta.css';
import '../styles/appointment-inbox.css';

export function ConsultationChat({ appointmentId, userId, otherName, photoUrl }: { appointmentId: string; userId: string; otherName: string; photoUrl?: string | null }) {
  const chat = useConsultationChat(appointmentId, userId);
  const [draft, setDraft] = useState('');
  const [sendError, setSendError] = useState('');
  const bottom = useRef<HTMLDivElement>(null);
  const lastMessageId = chat.messages.at(-1)?.id;
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'nearest' }); }, [lastMessageId]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSendError('');
    const content = draft;
    try { chat.notifyTyping(false); await chat.send(content); setDraft(current => current === content ? '' : current); }
    catch (reason: unknown) { setSendError(reason instanceof Error ? reason.message : 'No se pudo enviar el mensaje.'); }
  }
  return <section className="consultation-chat" aria-label="Chat de la consulta">
    <header><UserAvatar key={photoUrl} name={otherName} photoUrl={photoUrl} /><h2>{otherName}</h2><span role="status">{chat.connected ? 'Conectado' : chat.loading ? 'Conectando…' : 'Sin conexión'}</span></header>
    {(chat.error || sendError) && <div role="alert" className="consultation-chat-error"><p>{sendError || chat.error}</p><button type="button" disabled={chat.sending} onClick={() => { setSendError(''); chat.retry(); }}>Reintentar</button></div>}
    <div className="consultation-messages" role="log" aria-label="Mensajes" aria-live="polite" aria-relevant="additions">
      {chat.hasOlder && <button className="text-button" disabled={chat.olderBusy} onClick={() => { void chat.loadOlder(); }}>{chat.olderBusy ? 'Cargando…' : 'Mensajes anteriores'}</button>}
      {chat.loading && <p role="status">Cargando mensajes…</p>}
      {!chat.loading && chat.messages.length === 0 && !chat.error && <p className="consultation-chat-empty">Todavía no hay mensajes en esta consulta.</p>}
      {chat.messages.map(message => <article key={message.id} className={`consultation-message${message.sender_id === userId ? ' is-own' : ''}`}><p>{message.content}</p><footer>{message.sender_id === userId ? 'Tú' : otherName} · <time dateTime={message.created_at}>{appointmentDate(message.created_at)}</time></footer></article>)}
      <div ref={bottom} />
    </div>
    <p className="chat-typing" role="status">{chat.typing && chat.connected ? `${otherName} está escribiendo…` : ''}</p>
    {chat.room && !chat.room.can_write && <p className="consultation-chat-note">El chat está en modo de solo lectura por el estado o el horario de la cita.</p>}
    <form className="consultation-chat-form" onSubmit={event => { void submit(event); }}>
      <button className="chat-attach" type="button" aria-label="Adjuntar archivo (próximamente)" title="Adjuntos disponibles próximamente" onClick={() => setSendError('Los adjuntos estarán disponibles próximamente.')}>⌁</button>
      <label className="professional-sr-only" htmlFor="consultation-message">Mensaje</label>
      <textarea id="consultation-message" name="consultation_message" placeholder="Escribe un mensaje…" rows={2} maxLength={2000} value={draft} disabled={!chat.room?.can_write || !chat.connected || chat.sending} onBlur={() => chat.notifyTyping(false)} onChange={event => { setDraft(event.target.value); chat.notifyTyping(Boolean(event.target.value.trim())); }} />
      <button className="button primary" disabled={!draft.trim() || !chat.room?.can_write || !chat.connected || chat.sending} type="submit">{chat.sending ? 'Enviando…' : 'Enviar'}</button>
    </form>
  </section>;
}
