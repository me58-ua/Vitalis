import type { JitsiConstructor } from '../types/jitsi';

const scripts = new Map<string, Promise<JitsiConstructor>>();
export function jitsiOrigin(domain: string): URL {
  const url = new URL(domain.includes('://') ? domain : `https://${domain}`);
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('La dirección de videoconsulta recibida no es válida.');
  return url;
}
export function loadJitsi(domain: string): Promise<JitsiConstructor> {
  const url = jitsiOrigin(domain);
  const previous = scripts.get(url.origin);
  if (previous) return previous;
  const promise = new Promise<JitsiConstructor>((resolve, reject) => {
    const script = document.createElement('script');
    let finished = false;
    const finish = (error?: Error) => {
      if (finished) return;
      finished = true; clearTimeout(timeout); script.onload = null; script.onerror = null;
      if (error || !window.JitsiMeetExternalAPI) { script.remove(); reject(error ?? new Error('No se pudo iniciar Jitsi.')); }
      else resolve(window.JitsiMeetExternalAPI);
    };
    const timeout = setTimeout(() => finish(new Error('El servidor de videollamada no respondió.')), 15000);
    script.src = `${url.origin}/external_api.js`; script.async = true;
    script.onload = () => finish();
    script.onerror = () => finish(new Error('No se pudo cargar la videollamada. Comprueba la conexión y el certificado HTTPS del servidor.'));
    document.head.append(script);
  }).catch((error: unknown) => { scripts.delete(url.origin); throw error; });
  scripts.set(url.origin, promise);
  return promise;
}
