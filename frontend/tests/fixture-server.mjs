// Synthetic fixtures are restricted to test code. Never imported by src/.
import http from 'node:http';

export async function fixtureServer(origin = 'http://localhost:3000') {
  const state = { refreshes: 0, reads: 0, forbidden: false, failNotifications: false, empty: false, delayRefresh: 0, access: 'test-access', registrations: [], logins: 0, logouts: 0, failLogout: false, failSearch: false, searchEmpty: false, downloads: 0, failTotals: false, failAudits: false, auditEmpty: false, auditQueries: [], failAppointments: false, failCreateAppointment: false, failCancelAppointment: false, appointmentCreates: [], appointmentPatches: [], appointmentQueries: [] };
  const account = {
    id: '00000000-0000-4000-8000-000000000001', name: 'Cuenta de pruebas', dni: 'TEST-0001',
    username: 'test_user', email: 'test@example.invalid', tel: '000000000', birth_date: '1995-01-01',
    gender: null, role: 'patient', is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  };
  const participants = {
    patient: { ...account, id: '00000000-0000-4000-8000-000000000201', role: 'patient', name: 'Paciente sintético', username: 'patient_fixture' },
    professional: { ...account, id: '00000000-0000-4000-8000-000000000202', role: 'professional', name: 'Profesional sintético', username: 'professional_fixture' },
  };
  const appointments = [0, 1].map(index => ({ id: `00000000-0000-4000-8000-${String(301 + index).padStart(12, '0')}`, patient_id: participants.patient.id, professional_id: participants.professional.id, patient_name: participants.patient.name, professional_name: participants.professional.name, start_time: `2030-11-0${index + 2}T10:00:00Z`, end_time: `2030-11-0${index + 2}T11:00:00Z`, type: 'video', status: 'pending', reason: null }));
  const notification = {
    id: '00000000-0000-4000-8000-000000000002', type: 'test', title: 'Aviso de prueba', message: 'Mensaje sintético para verificar la interfaz.',
    entity: null, entity_id: null, scheduled_for: null, read_at: null, email_required: false, email_status: 'not_required', created_at: '2026-10-25T09:00:00Z',
  };
  const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', origin);
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
    if (path === '/admin/metrics/monthly') {
      if (account.role !== 'admin') return send(403, { detail: 'ADMIN_REQUIRED' });
      if (state.failTotals) return send(503, { detail: 'TEST_UNAVAILABLE' });
      return send(200, { timezone: 'Europe/Madrid', generated_at: '2030-11-15T12:00:00Z', month_start: '2030-10-31T23:00:00Z', month_end: '2030-11-30T23:00:00Z', month_start_date: '2030-11-01', month_end_date: '2030-11-30',
        users: { total: 8, current_month: 4, previous_month: 2, change_percent: 100 },
        patients: { total: 5, current_month: 0, previous_month: 2, change_percent: -100 },
        professionals: { total: 2, current_month: 1, previous_month: 0, change_percent: null },
        appointments: { total: 4, current_month: 4, previous_month: 2, change_percent: 100 },
        series: Array.from({ length: 6 }, (_, index) => ({ month: `2030-${String(index + 6).padStart(2, '0')}`, users: index === 5 ? 4 : index === 4 ? 2 : 0, patients: index === 4 ? 2 : 0, professionals: index === 5 ? 1 : 0, appointments: index === 5 ? 4 : index === 4 ? 2 : 0 })) });
    }
    if (path === '/admin/users') {
      if (account.role !== 'admin') return send(403, { detail: 'ADMIN_REQUIRED' });
      if (state.failTotals) return send(503, { detail: 'TEST_UNAVAILABLE' });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      if (params.get('page_size') === '20') {
        const item = participants[params.get('role')];
        return send(200, { users: item ? [item] : [], total: item ? 1 : 0, page: 1, page_size: 20 });
      }
      return send(200, { users: [account], total: params.get('role') === 'patient' ? 5 : params.get('role') === 'professional' ? 2 : 8, page: 1, page_size: 1 });
    }
    if (path === '/admin/appointments/upcoming-month') {
      const rows = appointments.filter(item => item.status === 'pending' || item.status === 'confirmed');
      return send(200, { appointments: rows.slice(0, 3), total: rows.length, period_start: '2030-11-01T00:00:00Z', period_end: '2030-12-01T00:00:00Z', timezone: 'Europe/Madrid' });
    }
    if (path === '/admin/appointments') {
      if (account.role !== 'admin') return send(403, { detail: 'ADMIN_REQUIRED' });
      if (req.method === 'POST') {
        if (state.failCreateAppointment) return send(409, { detail: 'TEST_CONFLICT' });
        const body = JSON.parse(raw); state.appointmentCreates.push(body);
        const item = { ...body, id: `00000000-0000-4000-8000-${String(400 + state.appointmentCreates.length).padStart(12, '0')}`, patient_name: participants.patient.name, professional_name: participants.professional.name, status: 'pending', reason: null };
        appointments.push(item); return send(201, item);
      }
      if (state.failAppointments) return send(503, { detail: 'TEST_UNAVAILABLE' });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      state.appointmentQueries.push(Object.fromEntries(params));
      let rows = appointments.filter(item => (!params.get('patient_id') || item.patient_id === params.get('patient_id')) && (!params.get('professional_id') || item.professional_id === params.get('professional_id')) && (!params.get('from_date') || item.start_time.slice(0, 10) >= params.get('from_date')) && (!params.get('to_date') || item.start_time.slice(0, 10) <= params.get('to_date')) && (params.get('upcoming_month') !== 'true' || ['pending', 'confirmed'].includes(item.status)));
      const page = Number(params.get('page') || 1), size = Number(params.get('page_size') || 20);
      return send(200, { appointments: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size });
    }
    if (path.startsWith('/admin/appointments/') && req.method === 'PATCH') {
      if (state.failCancelAppointment) return send(409, { detail: 'TEST_CONFLICT' });
      const item = appointments.find(item => item.id === path.split('/').at(-1));
      if (!item) return send(404, { detail: 'TEST_NOT_FOUND' });
      const body = JSON.parse(raw); state.appointmentPatches.push(body); Object.assign(item, body); return send(200, item);
    }
    if (path === '/admin/audit-logs') {
      if (account.role !== 'admin') return send(403, { detail: 'ADMIN_REQUIRED' });
      if (req.method !== 'GET') return send(405, { detail: 'METHOD_NOT_ALLOWED' });
      if (state.failAudits) return send(503, { detail: 'TEST_UNAVAILABLE' });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      state.auditQueries.push(Object.fromEntries(params));
      let rows = Array.from({ length: 21 }, (_, index) => ({ id: `00000000-0000-4000-8000-${String(index + 100).padStart(12, '0')}`, actor_id: account.id, actor_role: 'admin', patient_id: null, accion: index % 2 ? 'lectura' : 'modificacion', entidad: 'user_role', entidad_id: null, fecha_hora: '2026-10-30T12:00:00Z' }));
      for (const key of ['actor_id', 'actor_role', 'patient_id', 'accion', 'entidad', 'entidad_id']) {
        if (params.has(key)) rows = rows.filter(row => row[key] === params.get(key));
      }
      if (state.auditEmpty) rows = [];
      const page = Number(params.get('page') || 1), pageSize = Number(params.get('page_size') || 20);
      return send(200, { items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, page_size: pageSize });
    }
    if (path === '/auth/logout' && req.method === 'POST') {
      if (state.failLogout) return send(503, { detail: 'TEST_UNAVAILABLE' });
      state.logouts += 1;
      state.access = 'revoked-test-token';
      res.writeHead(204); res.end(); return;
    }
    if (path === '/health/documents/search') {
      if (state.failSearch) return send(503, { detail: 'TEST_UNAVAILABLE' });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      return send(200, {
        documents: state.searchEmpty ? [] : [{ id: notification.id, patient_user_id: account.id, tipo: 'informe', descripcion: 'Documento sintético de prueba', fecha_subida: '2026-10-26T09:00:00Z' }],
        total: state.searchEmpty ? 0 : 1, page: Number(params.get('page')), page_size: Number(params.get('page_size')),
      });
    }
    if (path === `/patients/me/health/documents/${notification.id}`) {
      state.downloads += 1;
      res.writeHead(200, { 'Content-Type': 'application/pdf' });
      res.end('Synthetic test-only file'); return;
    }
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
