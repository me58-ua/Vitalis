import { useCallback, useEffect, useRef, useState } from 'react';
import { getSpontaneousChat, getSpontaneousMessages, spontaneousChatError } from '../api/spontaneousChat';
import type { SpontaneousChat, SpontaneousMessage } from '../types/api';

function merge(before: SpontaneousMessage[], after: SpontaneousMessage[]) {
  return [...new Map([...before, ...after].map(message => [message.id, message])).values()]
    .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
}

export function useSpontaneousRoom(id: string) {
  const [room, setRoom] = useState<SpontaneousChat | null>(null);
  const [messages, setMessages] = useState<SpontaneousMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [hasOlder, setHasOlder] = useState(false);
  const [olderBusy, setOlderBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const olderAbort = useRef<AbortController | null>(null);
  const olderLock = useRef(false);
  useEffect(() => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let latest: string | undefined;
    let first = true;
    async function poll() {
      try {
        const [current, page] = await Promise.all([getSpontaneousChat(id, abort.signal), getSpontaneousMessages(id, abort.signal, latest ? { after_id: latest } : undefined)]);
        let added = page.messages, more = page.has_more;
        if (latest) while (more) {
          const cursor = added.at(-1)?.id;
          if (!cursor || cursor === latest) throw new Error('No se pudo recuperar el historial completo.');
          const next = await getSpontaneousMessages(id, abort.signal, { after_id: cursor });
          if (next.has_more && next.messages.at(-1)?.id === cursor) throw new Error('Historial incompleto.');
          added = [...added, ...next.messages]; more = next.has_more;
          if (next.has_more && next.messages.length === 0) throw new Error('Historial incompleto.');
        }
        if (abort.signal.aborted) return;
        if (first || !latest) { setHasOlder(page.has_more); first = false; }
        latest = added.at(-1)?.id ?? latest;
        setRoom(current); setMessages(previous => merge(previous, added)); setError('');
      } catch (error: unknown) { if (!abort.signal.aborted) setError(spontaneousChatError(error)); }
      finally { if (!abort.signal.aborted) { setLoading(false); timer = setTimeout(() => { void poll(); }, 3000); } }
    }
    void poll();
    return () => { abort.abort(); olderAbort.current?.abort(); clearTimeout(timer); };
  }, [id, revision]);
  const add = useCallback((message: SpontaneousMessage) => setMessages(previous => merge(previous, [message])), []);
  const retry = useCallback(() => setRevision(value => value + 1), []);
  async function loadOlder() {
    if (olderLock.current || !messages[0]) return;
    olderLock.current = true; setOlderBusy(true);
    const abort = new AbortController(); olderAbort.current = abort;
    try { const page = await getSpontaneousMessages(id, abort.signal, { before_id: messages[0].id }); if (!abort.signal.aborted) { setMessages(previous => merge(previous, page.messages)); setHasOlder(page.has_more); } }
    catch (error: unknown) { if (!abort.signal.aborted) setError(spontaneousChatError(error)); }
    finally { olderLock.current = false; if (!abort.signal.aborted) setOlderBusy(false); }
  }
  return { room, messages, loading, error, hasOlder, olderBusy, loadOlder, add, retry, setRoom };
}
