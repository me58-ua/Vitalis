// Synthetic fixtures are restricted to test code. Never imported by src/.
import http from 'node:http';

export async function fixtureServer() {
  const state = { refreshes: 0, reads: 0, forbidden: false, failNotifications: false, empty: false, delayRefresh: 0, access: 'test-access', registrations: [], logins: 0 };
  const account = {
    id: '00000000-0000-4000-8000-000000000001', name: 'Cuenta de pruebas', dni: 'TEST-0001',
    username: 'test_user', email: 'test@example.invalid', tel: '000000000', birth_date: '1995-01-01',
    gender: null, role: 'patient', is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  };
  const notification = {
    id: '00000000-0000-4000-8000-000000000002', type: 'test', title: 'Aviso de prueba', message: 'Mensaje sintético para verificar la interfaz.',
    entity: null, entity_id: null, scheduled_for: null, read_at: null, email_required: false, email_status: 'not_required', created_at: '2026-10-25T09:00:00Z',
  };
  const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', 'http://localhost:3000');
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
    let raw = '';
    for await (const part of req) raw += part;
    const send = (status, data) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(data)); };
    const path = new URL(req.url, 'http://fixture.invalid').pathname;
    if (path === '/auth/login') {
      state.logins += 1;
      const form = new URLSearchParams(raw);
      if (!req.headers['content-type']?.startsWith('application/x-www-form-urlencoded')) return send(422, { detail: 'FORM_REQUIRED' });
      if (form.get('username') !== 'test_user' || form.get('password') !== 'TestPassword!') return send(401, { detail: 'INVALID_CREDENTIALS' });
      state.access = 'test-access';
      return send(200, { access_token: state.access, refresh_token: 'test-refresh', token_type: 'bearer' });
    }
    if (path === '/auth/register') {
      state.registrations.push(JSON.parse(raw));
      return send(201, account);
    }
    if (path === '/auth/refresh') {
      state.refreshes += 1;
      if (state.delayRefresh) await new Promise((resolve) => setTimeout(resolve, state.delayRefresh));
      state.access = 'test-rotated';
      return send(200, { access_token: state.access, refresh_token: 'test-refresh-rotated', token_type: 'bearer' });
    }
    if (req.headers.authorization !== `Bearer ${state.access}`) return send(401, { detail: 'INVALID_CREDENTIALS' });
    if (path === '/auth/me') return send(200, account);
    if (state.forbidden) return send(403, { detail: 'PATIENT_REQUIRED' });
    if (state.failNotifications) return send(503, { detail: 'TEST_UNAVAILABLE' });
    if (path === '/notifications/unread-count') return send(200, { count: state.empty || notification.read_at ? 0 : 1 });
    if (path === '/notifications') return send(200, { notifications: state.empty ? [] : [notification], next_cursor: null });
    if (path === `/notifications/${notification.id}/read` && req.method === 'PATCH') {
      state.reads += 1; notification.read_at = '2026-10-25T10:00:00Z'; return send(200, notification);
    }
    send(404, { detail: 'TEST_NOT_FOUND' });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Test server address missing');
  return { state, account, notification, url: `http://127.0.0.1:${address.port}`, close: () => new Promise((resolve) => server.close(resolve)) };
}
