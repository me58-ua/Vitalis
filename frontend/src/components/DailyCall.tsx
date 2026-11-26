import { useEffect, useRef, useState } from 'react';
import { loadDaily, type DailyFrame } from '../api/daily';
import type { VideoJoin } from '../types/api';
import hangup from '../assets/figma/video/hangup.svg';

export function DailyCall({ access, onJoined, onClosed }: {
  access: VideoJoin;
  onJoined: () => void;
  onClosed: (intentional: boolean) => void;
}) {
  const parent = useRef<HTMLDivElement>(null);
  const frame = useRef<DailyFrame | null>(null);
  const intentionalExit = useRef(false);
  const [joinedAt, setJoinedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    if (joinedAt === null) return;
    const tick = setInterval(() => setElapsed(Math.max(0, Math.floor((Date.now() - joinedAt) / 1000))), 1000);
    return () => clearInterval(tick);
  }, [joinedAt]);

  useEffect(() => {
    let disposed = false;
    let closed = false;
    let joined = false;
    intentionalExit.current = false;
    void loadDaily().then(async daily => {
      if (disposed || !parent.current) return;
      const call = daily.createFrame(parent.current, {
        activeSpeakerMode: false,
        showLeaveButton: false,
        iframeStyle: { border: '0', width: '100%', height: '100%' },
      });
      frame.current = call;
      call.on('joined-meeting', () => {
        if (disposed) return;
        joined = true;
        setJoinedAt(Date.now());
        onJoined();
      });
      call.on('left-meeting', () => {
        if (disposed || closed) return;
        closed = true;
        if (!joined && !intentionalExit.current) {
          setError(previous => previous || 'Daily ha cerrado la sala antes de que pudieras unirte. Vuelve a preparar la llamada y comprueba los permisos de cámara y micrófono.');
          return;
        }
        onClosed(intentionalExit.current);
      });
      call.on('error', event => {
        if (disposed) return;
        setError(event.errorMsg === 'account-missing-payment-method'
          ? 'Daily requiere un método de pago en la cuenta que aloja la videollamada. Contacta con el administrador de Vitalis.'
          : 'Daily ha informado de un problema de conexión.');
      });
      call.on('camera-error', () => {
        if (!disposed) setError('Comprueba los permisos de cámara y micrófono del navegador.');
      });
      await call.join({ url: access.room_url, token: access.token, lang: 'es' });
    }).catch(() => {
      if (!disposed) setError(previous => previous || 'No se pudo conectar con Daily. Comprueba la conexión y vuelve a intentarlo.');
    });
    return () => {
      disposed = true;
      const call = frame.current;
      frame.current = null;
      void call?.destroy().catch(() => {});
    };
  }, [access, onJoined, onClosed]);

  function leave() {
    const call = frame.current;
    if (joinedAt === null || !call) {
      onClosed(false);
      return;
    }
    if (intentionalExit.current) return;
    intentionalExit.current = true;
    void call.leave().catch(() => {
      intentionalExit.current = false;
      setError('No se pudo terminar la llamada. Vuelve a intentarlo.');
    });
  }

  const minutes = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const seconds = String(elapsed % 60).padStart(2, '0');
  return <section className="daily-call" aria-label="Videollamada">
    <div className="daily-toolbar">
      <div className="daily-status" role="status">{joinedAt === null ? 'Comprueba tus dispositivos y pulsa Unirse dentro de la sala de Daily.' : `En llamada · ${minutes}:${seconds}`}</div>
      <button type="button" className="daily-hangup" onClick={leave}><img src={hangup} alt="" />{joinedAt === null ? 'Volver' : 'Terminar mi llamada'}</button>
    </div>
    <div ref={parent} className="daily-mount" />
    {error && <div className="daily-error" role="alert"><p>{error}</p><button type="button" className="button secondary" onClick={() => onClosed(false)}>Volver a preparar la llamada</button></div>}
  </section>;
}
