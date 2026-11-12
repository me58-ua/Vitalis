import { useEffect, useRef, useState } from 'react';
import { session } from '../api/session';
import { chatSocketUrl } from '../api/consultations';

export function useSpontaneousRealtime(id: string, userId: string, refresh: () => void) {
  const [connected, setConnected] = useState(false);
  const [typing, setTyping] = useState(false);
  const socket = useRef<WebSocket | null>(null);
  const lastTyping = useRef(0);
  useEffect(() => {
    let stopped = false;
    let retry: ReturnType<typeof setTimeout>;
    let typingTimer: ReturnType<typeof setTimeout>;
    function connect() {
      const token = session.read()?.access_token;
      if (!token || stopped) return;
      const url = chatSocketUrl(id, token).replace('/ws/chat/', '/ws/spontaneous-chat/');
      const current = new WebSocket(url); socket.current = current;
      current.onopen = () => { setConnected(true); refresh(); };
      current.onmessage = event => {
        let value; try { value = JSON.parse(String(event.data)); } catch { return; }
        if (value.type === 'changed') refresh();
        if (value.type === 'typing' && value.sender_id !== userId) {
          clearTimeout(typingTimer); setTyping(value.is_typing === true);
          typingTimer = setTimeout(() => setTyping(false), 3500);
        }
      };
      current.onclose = event => {
        if (stopped) return;
        setConnected(false); setTyping(false);
        if (![4401, 4403, 4404].includes(event.code)) retry = setTimeout(connect, 3000);
      };
      current.onerror = () => { /* Polling continues while the socket reconnects. */ };
    }
    connect();
    const heartbeat = setInterval(() => { if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: 'ping' })); }, 20000);
    return () => {
      stopped = true; clearInterval(heartbeat); clearTimeout(retry); clearTimeout(typingTimer);
      const current = socket.current;
      if (current) { current.onopen = null; current.onmessage = null; current.onclose = null; current.close(); }
      socket.current = null;
    };
  }, [id, userId, refresh]);
  function notifyTyping(active: boolean) {
    if (socket.current?.readyState !== WebSocket.OPEN || (active && Date.now() - lastTyping.current < 1000)) return;
    lastTyping.current = Date.now(); socket.current.send(JSON.stringify({ type: 'typing', is_typing: active }));
  }
  return { connected, typing, notifyTyping };
}
