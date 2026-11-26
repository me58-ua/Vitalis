// Controlled Daily Prebuilt test double used by the browser suite.
export const dailyFixture = String.raw`
window.__dailyTest ??= { disposals: 0 };
window.Daily = {
  createFrame(parent, options) {
    const listeners = new Map();
    const frame = document.createElement('iframe');
    frame.title = 'Videollamada de prueba';
    frame.srcdoc = '<html><body style="margin:0;background:#27313f;color:#e6eeff;font:20px sans-serif;display:grid;place-items:center;height:100vh"><p>Videollamada de prueba</p></body></html>';
    parent.append(frame);
    let timer;
    return {
      on(name, callback) { listeners.set(name, callback); },
      async join({ url, token }) {
        window.__dailyTest.correctAccess = token === 'test-daily-token'
          && url.startsWith('https://vitalis-fixture.daily.co/fixture-room-')
          && options.activeSpeakerMode === false
          && options.showLeaveButton === false;
        timer = setTimeout(() => listeners.get('joined-meeting')?.(), 100);
      },
      async leave() { listeners.get('left-meeting')?.(); },
      async destroy() {
        clearTimeout(timer);
        frame.remove();
        window.__dailyTest.disposals += 1;
      },
    };
  },
};
`;
