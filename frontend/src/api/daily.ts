const sdkUrl = 'https://unpkg.com/@daily-co/daily-js@0.94.0/dist/daily.js';

export interface DailyFrame {
  on(event: 'joined-meeting' | 'left-meeting' | 'camera-error', listener: () => void): void;
  on(event: 'error', listener: (event: { errorMsg?: string }) => void): void;
  join(options: { url: string; token: string; lang: 'es' }): Promise<unknown>;
  leave(): Promise<unknown>;
  destroy(): Promise<void>;
}

interface DailySdk {
  createFrame(parent: HTMLElement, options: {
    activeSpeakerMode: boolean;
    showLeaveButton: boolean;
    iframeStyle: Record<string, string>;
  }): DailyFrame;
}

declare global { interface Window { Daily?: DailySdk } }

export function validateDailyRoomUrl(value: string): void {
  const url = new URL(value);
  if (url.protocol !== 'https:' || !/^[a-z0-9-]+\.daily\.co$/.test(url.host)
      || url.username || url.password || !/^\/[\w-]+$/.test(url.pathname) || url.search || url.hash) {
    throw new Error('La dirección de videoconsulta recibida no es válida.');
  }
}

let sdk: Promise<DailySdk> | undefined;

export function loadDaily(): Promise<DailySdk> {
  sdk ??= new Promise<DailySdk>((resolve, reject) => {
    const script = document.createElement('script');
    const finish = () => {
      clearTimeout(timeout);
      script.onload = null;
      script.onerror = null;
      if (window.Daily?.createFrame) resolve(window.Daily);
      else {
        script.remove();
        reject(new Error('No se pudo cargar Daily.'));
      }
    };
    const timeout = setTimeout(finish, 15000);
    script.src = sdkUrl;
    script.async = true;
    script.crossOrigin = 'anonymous';
    script.onload = finish;
    script.onerror = finish;
    document.head.append(script);
  }).catch((error: unknown) => {
    sdk = undefined;
    throw error;
  });
  return sdk;
}
