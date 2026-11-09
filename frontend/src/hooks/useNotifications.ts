import { useCallback, useEffect, useRef, useState } from 'react';
import { getNotifications, getUnreadCount, markRead } from '../api/notifications';
import { errorMessage } from '../api/errors';
import type { NotificationPage } from '../types/api';

export function useNotifications(userId: string) {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  const [page, setPage] = useState<NotificationPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [countError, setCountError] = useState('');
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const controller = useRef<AbortController | null>(null);
  const marking = useRef(false);
  const retry = useCallback(() => {
    setLoading(true); setError(''); setCountError(''); setPendingId(null);
    setRevision((value) => value + 1);
  }, []);

  function toggle() {
    if (!open) { setLoading(true); setError(''); setPendingId(null); }
    setOpen(!open);
  }

  useEffect(() => {
    const abort = new AbortController();
    function refreshCount() {
      void getUnreadCount(abort.signal).then((value) => {
        if (!abort.signal.aborted) { setCount(value); setCountError(''); }
      }).catch((error: unknown) => {
        if (!abort.signal.aborted) setCountError(errorMessage(error));
      });
    }
    refreshCount();
    const interval = window.setInterval(refreshCount, 30000);
    window.addEventListener('focus', refreshCount);
    return () => {
      abort.abort(); window.clearInterval(interval); window.removeEventListener('focus', refreshCount);
    };
  }, [userId, revision, open]);

  useEffect(() => {
    if (!open) return;
    const abort = new AbortController();
    controller.current = abort;
    function refreshPage() {
      if (marking.current) return;
      void getNotifications(abort.signal).then((data) => {
        if (!abort.signal.aborted) { setPage(data); setError(''); }
      }).catch((error: unknown) => {
        if (!abort.signal.aborted) setError(errorMessage(error));
      }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    }
    refreshPage();
    const interval = window.setInterval(refreshPage, 30000);
    window.addEventListener('focus', refreshPage);
    return () => {
      abort.abort(); marking.current = false;
      window.clearInterval(interval); window.removeEventListener('focus', refreshPage);
    };
  }, [open, userId, revision]);

  async function read(id: string) {
    const abort = controller.current;
    if (!abort || abort.signal.aborted || marking.current) return;
    marking.current = true; setPendingId(id); setError('');
    try {
      const updated = await markRead(id, abort.signal);
      if (abort.signal.aborted) return;
      setPage((previous) => previous ? {
        ...previous, notifications: previous.notifications.map((item) => item.id === updated.id ? updated : item),
      } : previous);
      const unread = await getUnreadCount(abort.signal);
      if (!abort.signal.aborted) setCount(unread);
    } catch (error: unknown) { if (!abort.signal.aborted) setError(errorMessage(error)); }
    finally { if (!abort.signal.aborted) { marking.current = false; setPendingId(null); } }
  }

  return { open, toggle, count, page, loading, error, countError, pendingId, retry, read };
}
