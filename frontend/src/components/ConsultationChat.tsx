import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useConsultationChat } from '../hooks/useConsultationChat';
import { appointmentDate } from './AppointmentSummary';
import { UserAvatar } from './UserAvatar';
import attachmentIcon from '../assets/figma/video/chat-attachment.svg';
import sendIcon from '../assets/figma/video/chat-send.svg';
import moreIcon from '../assets/figma/video/chat-more.svg';
import '../styles/videoconsulta.css';
import '../styles/appointment-inbox.css';

export function ConsultationChat({ appointmentId, userId, otherName, photoUrl, variant = 'inbox' }: { appointmentId: string; userId: string; otherName: string; photoUrl?: string | null; variant?: 'inbox' | 'call' }) {
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
  const call = variant === 'call';
  const connectionLabel = chat.connected ? 'Conectado' : chat.loading ? 'Conectando…' : 'Sin conexión';
  return <section className={`consultation-chat${call ? ' consultation-chat-call' : ''}`} aria-label="Chat de la consulta">
    <header>{!call && <UserAvatar key={photoUrl} name={otherName} photoUrl={photoUrl} />}<h2>{call ? 'Chat Seguro' : otherName}</h2><span className={`consultation-chat-connection${chat.connected ? ' is-connected' : ''}`} role="status" aria-label={connectionLabel} title={connectionLabel}>{call ? <span className="professional-sr-only">{connectionLabel}</span> : connectionLabel}</span>{call && <details className="consultation-chat-details"><summary aria-label="Información del chat"><img src={moreIcon} alt="" /></summary><div><strong>Con {otherName}</strong><p>{connectionLabel}. Solo los participantes de esta videoconsulta pueden acceder a los mensajes.</p><p>Se puede escribir durante la cita. Al finalizar, el historial queda en modo de solo lectura.</p></div></details>}</header>
    {(chat.error || sendError) && <div role="alert" className="consultation-chat-error"><p>{sendError || chat.error}</p><button type="button" disabled={chat.sending} onClick={() => { setSendError(''); chat.retry(); }}>Reintentar</button></div>}
    <div className="consultation-messages" role="log" aria-label="Mensajes" aria-live="polite" aria-relevant="additions">
      {chat.hasOlder && <button className="text-button" disabled={chat.olderBusy} onClick={() => { void chat.loadOlder(); }}>{chat.olderBusy ? 'Cargando…' : 'Mensajes anteriores'}</button>}
      {chat.loading && <p role="status">Cargando mensajes…</p>}
      {!chat.loading && chat.messages.length === 0 && !chat.error && <p className="consultation-chat-empty">Todavía no hay mensajes en esta consulta.</p>}
      {chat.messages.map(message => <article key={message.id} className={`consultation-message${message.sender_id === userId ? ' is-own' : ''}`}><p>{message.content}</p><footer>{call ? <><time dateTime={message.created_at} title={appointmentDate(message.created_at)}>{new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Europe/Madrid' }).format(new Date(message.created_at))}</time> - {message.sender_id === userId ? 'Tú' : otherName}</> : <>{message.sender_id === userId ? 'Tú' : otherName} · <time dateTime={message.created_at}>{appointmentDate(message.created_at)}</time></>}</footer></article>)}
      <div ref={bottom} />
    </div>
    <p className="chat-typing" role="status">{chat.typing && chat.connected ? `${otherName} está escribiendo…` : ''}</p>
    {chat.room && !chat.room.can_write && <p className="consultation-chat-note">El chat está en modo de solo lectura por el estado o el horario de la cita.</p>}
    <form className="consultation-chat-form" onSubmit={event => { void submit(event); }}>
      <button className="chat-attach" type="button" aria-label="Adjuntar archivo (próximamente)" title="Adjuntos disponibles próximamente" onClick={() => setSendError('Los adjuntos estarán disponibles próximamente.')}>{call ? <img src={attachmentIcon} alt="" /> : '⌁'}</button>
      <label className="professional-sr-only" htmlFor="consultation-message">Mensaje</label>
      <textarea id="consultation-message" name="consultation_message" placeholder="Escribe un mensaje…" rows={call ? 1 : 2} maxLength={2000} value={draft} disabled={!chat.room?.can_write || !chat.connected || chat.sending} onBlur={() => chat.notifyTyping(false)} onChange={event => { setDraft(event.target.value); chat.notifyTyping(Boolean(event.target.value.trim())); }} />
      <button className="button primary" aria-label={chat.sending ? 'Enviando…' : 'Enviar mensaje'} disabled={!draft.trim() || !chat.room?.can_write || !chat.connected || chat.sending} type="submit">{call ? <img src={sendIcon} alt="" /> : chat.sending ? 'Enviando…' : 'Enviar'}</button>
    </form>
  </section>;
}
