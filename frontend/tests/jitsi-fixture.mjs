// Controlled IFrame API test double. Never imported by application code.
export const jitsiFixture = String.raw`
window.__jitsiTest = window.__jitsiTest || { commands: [], disposals: 0, instances: 0 };
window.JitsiMeetExternalAPI = class {
  constructor(domain, options) {
    this.listeners = new Map(); this.audio = false; this.video = false; this.share = false;
    this.frame = document.createElement('iframe');
    this.frame.title = 'Videollamada de prueba';
    this.frame.srcdoc = '<html><body style="margin:0;background:#27313f;color:#e6eeff;font:20px sans-serif;display:grid;place-items:center;height:100vh"><p>Videollamada de prueba</p></body></html>';
    options.parentNode.append(this.frame);
    window.__jitsiTest.instances += 1;
    window.__jitsiTest.correctAccess = options.jwt === 'test-video-jwt' && options.roomName.startsWith('fixture-room-') && domain === 'jitsi.fixture.invalid';
    this.timer = setTimeout(() => this.emit('videoConferenceJoined', {}), 100);
  }
  addListener(name, callback) { this.listeners.set(name, callback); }
  removeListener(name) { this.listeners.delete(name); }
  emit(name, value) { this.listeners.get(name)?.(value); }
  executeCommand(command) {
    window.__jitsiTest.commands.push(command);
    if (command === 'toggleAudio') { this.audio = !this.audio; this.emit('audioMuteStatusChanged', { muted: this.audio }); }
    if (command === 'toggleVideo') { this.video = !this.video; this.emit('videoMuteStatusChanged', { muted: this.video }); }
    if (command === 'toggleShareScreen') { this.share = !this.share; this.emit('screenSharingStatusChanged', { on: this.share }); }
    if (command === 'hangup') this.emit('videoConferenceLeft', {});
  }
  dispose() { clearTimeout(this.timer); this.frame.remove(); window.__jitsiTest.disposals += 1; }
};
`;
