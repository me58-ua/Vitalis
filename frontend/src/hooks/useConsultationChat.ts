import { useEffect, useRef, useState } from 'react';
import { chatSocketUrl, consultationError, getChatMessages, getChatRoom } from '../api/consultations';
import { session } from '../api/session';
import type { ChatMessage, ChatRoom } from '../types/api';

function socketMessage(value: unknown, appointmentId: string): ChatMessage | null {
  if (typeof value !== 'object' || value === null || !('type' in value) || value.type !== 'message'
    || !('id' in value) || typeof value.id !== 'string' || !('sender_id' in value) || typeof value.sender_id !== 'string'
    || !('content' in value) || typeof value.content !== 'string' || !('created_at' in value) || typeof value.created_at !== 'string'
    || !Number.isFinite(Date.parse(value.created_at))) return null;
  return { id: value.id, sender_id: value.sender_id, content: value.content, created_at: value.created_at, appointment_id: appointmentId };
}
function merge(previous: ChatMessage[], incoming: ChatMessage[]) {
  const items = new Map(previous.map(item => [item.id, item]));
  incoming.forEach(item => items.set(item.id, item));
  return [...items.values()].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id.localeCompare(b.id));
}
interface PendingMessage { content: string; resolve: () => void; reject: (error: Error) => void; timeout: ReturnType<typeof setTimeout> }

export function useConsultationChat(appointmentId: string, userId: string) {
  const [room, setRoom] = useState<ChatRoom | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [olderBusy, setOlderBusy] = useState(false);
  const [hasOlder, setHasOlder] = useState(false);
  const [revision, setRevision] = useState(0);
  const socket = useRef<WebSocket | null>(null);
  const pending = useRef<PendingMessage | null>(null);
  const oldest = useRef<string | undefined>(undefined);
  const latest = useRef<string | undefined>(undefined);
  const canWrite = useRef(false);
  const olderLock = useRef(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const abort = new AbortController(); controller.current = abort;
    let currentSocket: WebSocket | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    const heartbeat = setInterval(() => {
      if (currentSocket?.readyState === WebSocket.OPEN) currentSocket.send(JSON.stringify({ type: 'ping' }));
    }, 20000);
    function rejectPending(message: string) {
      const item = pending.current;
      if (item) { clearTimeout(item.timeout); pending.current = null; item.reject(new Error(message)); }
      if (!abort.signal.aborted) setSending(false);
    }
    async function synchronize() {
      const metadata = await getChatRoom(appointmentId, abort.signal);
      if (abort.signal.aborted) return;
      canWrite.current = metadata.can_write; setRoom(metadata);
      if (!latest.current) {
        const rows = await getChatMessages(appointmentId, abort.signal);
        if (abort.signal.aborted) return;
        setMessages(previous => merge(previous, rows));
        oldest.current = rows[0]?.id; latest.current = rows.at(-1)?.id;
        setHasOlder(rows.length === 50);
      } else {
        // Recover every missed page after a disconnect, not just the first 50.
        for (;;) {
          const before: string | undefined = latest.current;
          const rows = await getChatMessages(appointmentId, abort.signal, { after_id: before });
          if (abort.signal.aborted) return;
          setMessages(previous => merge(previous, rows));
          if (rows.length) latest.current = rows.at(-1)?.id;
          if (rows.length < 50 || latest.current === before) break;
        }
      }
    }
    async function connect() {
      try {
        await synchronize();
        if (abort.signal.aborted) return;
        setLoading(false);
        const token = session.read()?.access_token;
        if (!token) throw new Error('Inicia sesión para acceder al chat.');
        currentSocket = new WebSocket(chatSocketUrl(appointmentId, token)); socket.current = currentSocket;
        currentSocket.onopen = () => {
          if (abort.signal.aborted) return;
          setConnected(true); setError('');
          // A message can arrive between the initial REST request and socket open.
          void synchronize().catch((reason: unknown) => { if (!abort.signal.aborted) setError(consultationError(reason)); });
        };
        currentSocket.onmessage = event => {
          if (abort.signal.aborted) return;
          let value: unknown;
          try { value = JSON.parse(String(event.data)); } catch { return; }
          const message = socketMessage(value, appointmentId);
          if (message) {
            latest.current = message.id;
            setMessages(previous => merge(previous, [message]));
            const sent = pending.current;
            if (message.sender_id === userId && sent?.content === message.content) {
              clearTimeout(sent.timeout); pending.current = null; setSending(false); sent.resolve();
            }
          } else if (typeof value === 'object' && value !== null && 'type' in value && value.type === 'error') {
            rejectPending('El servidor no aceptó el mensaje. Revisa el estado del chat antes de reenviar.');
            setError('No se pudo enviar el mensaje. El chat puede estar fuera de plazo o haber cambiado de estado.');
            void synchronize().catch(() => { /* Keep the existing visible error. */ });
          }
        };
        currentSocket.onclose = event => {
          if (abort.signal.aborted) return;
          setConnected(false); rejectPending('Se perdió la conexión antes de confirmar el envío. Actualiza el chat antes de reenviar.');
          if (event.code === 4403 || event.code === 4404) { setError('Ya no tienes acceso a este chat.'); return; }
          if (attempts < 3) {
            attempts += 1; setError('Conexión interrumpida. Reconectando…');
            reconnect = setTimeout(() => { void connect(); }, 1000 * 2 ** (attempts - 1));
          } else setError('No se pudo recuperar la conexión. Pulsa Reintentar.');
        };
        currentSocket.onerror = () => { if (!abort.signal.aborted) setError('No se pudo conectar el chat. Comprueba la conexión con el servidor.'); };
      } catch (reason: unknown) {
        if (!abort.signal.aborted) { setLoading(false); setError(consultationError(reason)); }
      }
    }
    void connect();
    return () => {
      abort.abort(); clearInterval(heartbeat); clearTimeout(reconnect);
      if (currentSocket) { currentSocket.onclose = null; currentSocket.onmessage = null; currentSocket.onopen = null; currentSocket.onerror = null; currentSocket.close(); }
      socket.current = null; canWrite.current = false;
      rejectPending('Has salido del chat.');
    };
  }, [appointmentId, userId, revision]);

  function send(content: string): Promise<void> {
    const text = content.trim();
    if (!text || text.length > 2000) return Promise.reject(new Error('Escribe un mensaje de 1 a 2000 caracteres.'));
    if (pending.current || !canWrite.current || socket.current?.readyState !== WebSocket.OPEN) return Promise.reject(new Error('El chat no está disponible para enviar en este momento.'));
    setSending(true);
    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        pending.current = null; setSending(false);
        reject(new Error('No se pudo confirmar el envío. Actualiza el chat antes de reenviar para evitar duplicados.'));
      }, 15000);
      pending.current = { content: text, resolve, reject, timeout };
      try { socket.current?.send(JSON.stringify({ type: 'message', content: text })); }
      catch { clearTimeout(timeout); pending.current = null; setSending(false); reject(new Error('No se pudo enviar el mensaje.')); }
    });
  }
  async function loadOlder() {
    const abort = controller.current;
    if (olderLock.current || !oldest.current || !abort || abort.signal.aborted) return;
    olderLock.current = true; setOlderBusy(true);
    try {
      const rows = await getChatMessages(appointmentId, abort.signal, { before_id: oldest.current });
      if (!abort.signal.aborted) { setMessages(previous => merge(previous, rows)); oldest.current = rows[0]?.id ?? oldest.current; setHasOlder(rows.length === 50); }
    } catch (reason: unknown) { if (!abort.signal.aborted) setError(consultationError(reason)); }
    finally { olderLock.current = false; if (!abort.signal.aborted) setOlderBusy(false); }
  }
  return { room, messages, loading, connected, error, sending, olderBusy, hasOlder, send, loadOlder,
    retry: () => { setError(''); setLoading(true); setConnected(false); setSending(false); setRevision(value => value + 1); } };
}
