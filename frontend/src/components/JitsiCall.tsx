import { useEffect, useRef, useState } from 'react';
import { jitsiOrigin, loadJitsi } from '../api/jitsi';
import type { VideoJoin } from '../types/api';
import type { JitsiCommand, JitsiInstance, JitsiListener } from '../types/jitsi';
import microphone from '../assets/figma/video/microphone.svg';
import camera from '../assets/figma/video/camera.svg';
import share from '../assets/figma/video/share.svg';
import hangup from '../assets/figma/video/hangup.svg';

export function JitsiCall({ access, displayName, onJoined, onClosed }: { access: VideoJoin; displayName: string; onJoined: () => void; onClosed: (intentional: boolean) => void }) {
  const parent = useRef<HTMLDivElement>(null);
  const instance = useRef<JitsiInstance | null>(null);
  const intentionalExit = useRef(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [audioMuted, setAudioMuted] = useState(false);
  const [videoMuted, setVideoMuted] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [joinedAt, setJoinedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (joinedAt === null) return;
    const tick = setInterval(() => setElapsed(Math.max(0, Math.floor((Date.now() - joinedAt) / 1000))), 1000);
    return () => clearInterval(tick);
  }, [joinedAt]);
  useEffect(() => {
    let disposed = false, closed = false;
    let api: JitsiInstance | null = null;
    const listeners: Array<[string, JitsiListener]> = [];
    const end = () => { if (!disposed && !closed) { closed = true; onClosed(intentionalExit.current); } };
    const listen = (name: string, callback: JitsiListener) => { api?.addListener(name, callback); listeners.push([name, callback]); };
    void Promise.resolve().then(() => loadJitsi(access.domain)).then(Constructor => {
      if (disposed || !parent.current) return;
      api = new Constructor(jitsiOrigin(access.domain).host, {
        parentNode: parent.current, roomName: access.room_name, jwt: access.jwt,
        width: '100%', height: '100%', lang: 'es', userInfo: { displayName },
        configOverwrite: { toolbarButtons: [], disableDeepLinking: true, prejoinConfig: { enabled: true } },
      });
      instance.current = api;
      listen('videoConferenceJoined', () => { if (!disposed) { setConnected(true); setJoinedAt(Date.now()); onJoined(); } });
      listen('videoConferenceLeft', end); listen('readyToClose', end);
      listen('audioMuteStatusChanged', value => { if (!disposed && typeof value === 'object' && value !== null && 'muted' in value && typeof value.muted === 'boolean') setAudioMuted(value.muted); });
      listen('videoMuteStatusChanged', value => { if (!disposed && typeof value === 'object' && value !== null && 'muted' in value && typeof value.muted === 'boolean') setVideoMuted(value.muted); });
      listen('screenSharingStatusChanged', value => { if (!disposed && typeof value === 'object' && value !== null && 'on' in value && typeof value.on === 'boolean') setSharing(value.on); });
      listen('cameraError', () => { if (!disposed) setError('No se puede acceder a la cámara. Revisa sus permisos o continúa solo con audio.'); });
      listen('micError', () => { if (!disposed) setError('No se puede acceder al micrófono. Revisa los permisos del navegador.'); });
      listen('errorOccurred', () => { if (!disposed) setError('Jitsi ha informado de un problema de conexión. Comprueba la red y los permisos del navegador.'); });
    }).catch(() => { if (!disposed) setError('No se pudo cargar Jitsi. Comprueba la conexión y que el certificado HTTPS del servidor de videollamada sea de confianza.'); });
    return () => {
      disposed = true; instance.current = null;
      if (api) { for (const [name, listener] of listeners) api.removeListener(name, listener); api.dispose(); }
    };
  }, [access, displayName, onJoined, onClosed]);

  function command(name: JitsiCommand) {
    try { if (name === 'hangup') intentionalExit.current = true; instance.current?.executeCommand(name); }
    catch { setError('No se pudo realizar esta acción en la llamada.'); }
  }
  return <section className="jitsi-call" aria-label="Videollamada">
    <div className="jitsi-status" role="status">{connected ? <>En llamada · {String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}</> : 'Preparando cámara y micrófono…'}</div>
    <div ref={parent} className="jitsi-mount" />
    {error && <div className="jitsi-error" role="alert"><p>{error}</p><p><a href={jitsiOrigin(access.domain).origin} target="_blank" rel="noopener noreferrer">Abrir el servidor de videollamada para comprobar su conexión</a></p><button type="button" className="button secondary" onClick={() => onClosed(false)}>Volver a preparar la llamada</button></div>}
    <div className="jitsi-controls" aria-label="Controles de la llamada">
      <button type="button" disabled={!connected} aria-pressed={audioMuted} onClick={() => command('toggleAudio')}><span><img src={microphone} alt="" /></span>{audioMuted ? 'Activar audio' : 'Silenciar'}</button>
      <button type="button" disabled={!connected} aria-pressed={!videoMuted} onClick={() => command('toggleVideo')}><span><img src={camera} alt="" /></span>{videoMuted ? 'Activar cámara' : 'Cámara'}</button>
      <button type="button" disabled={!connected} aria-pressed={sharing} onClick={() => command('toggleShareScreen')}><span><img src={share} alt="" /></span>{sharing ? 'Dejar de compartir' : 'Compartir'}</button>
      <button type="button" className="jitsi-hangup" onClick={() => command('hangup')}><span><img src={hangup} alt="" /></span>{connected ? 'Terminar mi llamada' : 'Volver'}</button>
    </div>
  </section>;
}
