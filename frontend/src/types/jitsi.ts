// Frontend-only surface of the official Jitsi IFrame API; not a REST schema.
export type JitsiListener = (event: unknown) => void;
export type JitsiCommand = 'toggleAudio' | 'toggleVideo' | 'toggleShareScreen' | 'hangup';
export interface JitsiInstance {
  executeCommand(command: JitsiCommand): void;
  addListener(event: string, listener: JitsiListener): void;
  removeListener(event: string, listener: JitsiListener): void;
  dispose(): void;
}
export interface JitsiOptions {
  roomName: string; jwt: string; parentNode: HTMLElement; width: string; height: string; lang: string;
  userInfo: { displayName: string };
  configOverwrite: { toolbarButtons: string[]; disableDeepLinking: boolean; prejoinConfig: { enabled: boolean } };
}
export type JitsiConstructor = new (domain: string, options: JitsiOptions) => JitsiInstance;
declare global { interface Window { JitsiMeetExternalAPI?: JitsiConstructor } }
