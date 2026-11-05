import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import { fixtureServer } from './fixture-server.mjs';

test('Axios follows authentication and notification contracts', async (t) => {
  const stored = new Map();
  globalThis.window = { sessionStorage: { getItem: key => stored.get(key) ?? null, setItem: (key, value) => stored.set(key, value), removeItem: key => stored.delete(key) } };
  t.after(() => { delete globalThis.window; });
  const fixture = await fixtureServer();
  t.after(fixture.close);
  const root = fileURLToPath(new URL('../', import.meta.url));
  const output = path.join(root, 'test-results', 'client');
  await mkdir(output, { recursive: true });
  for (const name of ['client', 'session', 'auth', 'notifications', 'errors', 'admin', 'adminUserErrors', 'professional', 'professionalErrors', 'consultations', 'jitsi']) {
    const source = (await readFile(path.join(root, 'src/api', `${name}.ts`), 'utf8'))
      .replace('import.meta.env.VITE_API_BASE_URL', JSON.stringify(fixture.url));
    const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
      .replace(/(from\s+['"])(\.[^'"]+)(['"])/g, '$1$2.js$3');
    await writeFile(path.join(output, `${name}.js`), compiled);
  }
  const load = (name) => import(pathToFileURL(path.join(output, `${name}.js`)).href);
  const { api, publicApi } = await load('client');
  api.defaults.proxy = false; publicApi.defaults.proxy = false;
  const auth = await load('auth');
  const notifications = await load('notifications');
  const { session } = await load('session');
  const { errorMessage } = await load('errors');
  const { adminUserError } = await load('adminUserErrors');
  const admin = await load('admin');
  const professional = await load('professional');
  const consultations = await load('consultations');
  const { jitsiOrigin } = await load('jitsi');

  await t.test('URL-encoded login and account lookup', async () => {
    const tokens = await auth.login('test_user', 'TestPassword!');
    session.replace(tokens);
    assert.equal((await auth.currentUser()).id, fixture.account.id);
    assert.equal(tokens.token_type, 'bearer');
  });
  await t.test('browser storage restores the session after module reload', async () => {
    const reloaded = await import(`${pathToFileURL(path.join(output, 'session.js')).href}?reload=1`);
    assert.deepEqual(reloaded.session.read(), session.read());
    assert.equal(stored.size, 1);
  });
  await t.test('invalid credentials produce a Spanish error', async () => {
    await assert.rejects(auth.login('test_user', 'incorrect'), (error) => {
      assert.match(errorMessage(error), /credenciales/); return true;
    });
  });
  await t.test('parallel 401 responses share one rotating refresh', async () => {
    fixture.state.access = 'expired';
    fixture.state.delayRefresh = 40;
    const controller = new AbortController();
    const [count, page] = await Promise.all([
      notifications.getUnreadCount(controller.signal), notifications.getNotifications(controller.signal),
    ]);
    assert.equal(count, 1); assert.equal(page.notifications.length, 1);
    assert.equal(fixture.state.refreshes, 1);
    assert.equal(session.read().refresh_token, 'test-refresh-rotated');
    assert.equal(JSON.parse(stored.get('vitalis.session')).refresh_token, 'test-refresh-rotated');
  });
  await t.test('403 does not refresh or clear the session', async () => {
    fixture.state.forbidden = true;
    await assert.rejects(notifications.getUnreadCount(new AbortController().signal), (error) => {
      assert.equal(error.response.status, 403); assert.match(errorMessage(error), /permiso/); return true;
    });
    assert.equal(fixture.state.refreshes, 1); assert.ok(session.read());
    fixture.state.forbidden = false;
  });
  await t.test('mark-as-read uses the UUID path and real response', async () => {
    const item = await notifications.markRead(fixture.notification.id, new AbortController().signal);
    assert.ok(item.read_at); assert.equal(fixture.state.reads, 1);
    assert.equal(await notifications.getUnreadCount(new AbortController().signal), 0);
  });
  await t.test('a temporary refresh failure preserves the saved login for retry', async () => {
    const before = session.read();
    fixture.state.access = 'expired-for-network-test'; fixture.state.failRefresh = true;
    await assert.rejects(notifications.getUnreadCount(new AbortController().signal));
    assert.deepEqual(session.read(), before);
    assert.equal(stored.has('vitalis.session'), true);
    fixture.state.failRefresh = false;
    await notifications.getUnreadCount(new AbortController().signal);
  });
  await t.test('empty and failed responses never fabricate notifications', async () => {
    fixture.state.empty = true;
    assert.deepEqual((await notifications.getNotifications(new AbortController().signal)).notifications, []);
    fixture.state.failNotifications = true;
    await assert.rejects(notifications.getNotifications(new AbortController().signal));
    fixture.state.failNotifications = false;
  });
  await t.test('logout during refresh cannot restore the old session', async () => {
    fixture.state.access = 'expired-again'; fixture.state.delayRefresh = 100;
    const request = notifications.getUnreadCount(new AbortController().signal);
    await new Promise((resolve) => setTimeout(resolve, 30));
    session.replace(null);
    await assert.rejects(request);
    assert.equal(session.read(), null);
    assert.equal(stored.has('vitalis.session'), false);
  });
  await t.test('admin user CRUD sends nested profiles, paginates, and explains conflicts in Spanish', async () => {
    fixture.account.role = 'admin'; fixture.state.userManagement = true; fixture.state.delayRefresh = 0;
    session.replace(await auth.login('test_user', 'TestPassword!'));
    const signal = new AbortController().signal;
    const page = await admin.getAdminUsers({ role: 'patient', page: 2, page_size: 20 }, signal);
    assert.equal(page.users.length, 1); assert.equal(page.total, 21); assert.equal(page.page, 2);
    const payload = { name: 'Synthetic create', dni: 'TEST-NEW', username: 'new_test', email: 'new@example.invalid', tel: '000000000', birth_date: '1990-01-01', role: 'patient', password: 'TestPassword!', patient_profile: { height_cm: 175, timezone: 'Europe/Madrid' } };
    const created = await admin.createAdminUser(payload, signal);
    assert.equal(created.patient_profile.height_cm, 175);
    assert.deepEqual(fixture.state.userWrites.at(-1).patient_profile, payload.patient_profile);
    assert.equal((await admin.getAdminUser(created.id, signal)).username, payload.username);
    const updated = await admin.updateAdminUser(created.id, { name: 'Edited', patient_profile: { weight_kg: 70 } }, signal);
    assert.equal(updated.name, 'Edited'); assert.equal(fixture.state.userWrites.at(-1).password, undefined);
    for (const [code, text, field] of [['DUPLICATE_DNI', /DNI/, 'dni'], ['DUPLICATE_EMAIL', /correo/, 'email'], ['DUPLICATE_USERNAME', /nombre de usuario/, 'username'], ['DUPLICATE_LICENSE_NUMBER', /colegiación/, 'license_number']]) {
      fixture.state.userFailure = { status: 409, detail: code };
      await assert.rejects(admin.createAdminUser(payload, signal), error => {
        const translated = adminUserError(error, 'save'); assert.match(translated.summary, text); assert.ok(translated.fields[field]); return true;
      });
    }
    await assert.rejects(admin.deleteAdminUser(created.id, signal), error => { assert.match(adminUserError(error, 'delete').summary, /registros relacionados/); return true; });
    fixture.state.userFailure = { status: 422, detail: [{ loc: ['body', 'patient_profile', 'height_cm'], type: 'greater_than_equal', ctx: { ge: 100 } }, { loc: ['body', 'professional_profile', 'license_number'], type: 'missing' }] };
    await assert.rejects(admin.createAdminUser(payload, signal), error => {
      const translated = adminUserError(error, 'save'); assert.match(translated.fields.height_cm, /mínimo es 100/); assert.match(translated.fields.license_number, /obligatorio/); return true;
    });
    for (const [status, text] of [[403, /administrador/], [404, /ya no existe/], [429, /demasiadas/], [503, /servidor/]]) {
      fixture.state.userFailure = { status, detail: 'DO_NOT_EXPOSE_INTERNAL_DETAIL' };
      await assert.rejects(admin.createAdminUser(payload, signal), error => {
        const message = adminUserError(error, 'save').summary; assert.match(message, text); assert.ok(!message.includes('DO_NOT_EXPOSE')); return true;
      });
    }
    fixture.state.userFailure = null;
    await admin.deleteAdminUser(created.id, signal);
    await assert.rejects(admin.getAdminUser(created.id, signal));
  });
  await t.test('professional API separates appointment motive from cancellation and keeps English transport enums', async () => {
    fixture.account.role = 'professional';
    const signal = new AbortController().signal;
    const dashboard = await professional.getProfessionalDashboard(signal);
    assert.equal(dashboard.weekly_distribution.length, 7);
    assert.equal(dashboard.timezone, 'Europe/Madrid');
    assert.ok(dashboard.upcoming_appointments.every(item => ['confirmed'].includes(item.status)));
    const payload = { patient_id: '00000000-0000-4000-8000-000000000201', start_time: '2030-11-05T10:00:00Z', end_time: '2030-11-05T10:30:00Z', type: 'in_person', appointment_reason: 'Motivo original sintético' };
    await professional.createProfessionalAppointment(fixture.account.id, payload, signal);
    assert.deepEqual(fixture.state.professionalCreates.at(-1), payload);
    let page = await professional.getProfessionalAppointments({ page: 1, page_size: 20, upcoming_only: false }, signal);
    const item = page.appointments.find(item => item.appointment_reason === payload.appointment_reason);
    assert.ok(item);
    await professional.cancelProfessionalAppointment(fixture.account.id, item.id, 'Cancelación sintética', signal);
    page = await professional.getProfessionalAppointments({ upcoming_only: false, status: 'cancelled' }, signal);
    const cancelled = page.appointments.find(row => row.id === item.id);
    assert.equal(cancelled.appointment_reason, payload.appointment_reason);
    assert.equal(cancelled.cancellation_reason, 'Cancelación sintética');
    assert.deepEqual(fixture.state.professionalCancels.at(-1), { cancellation_reason: 'Cancelación sintética' });
    assert.ok((await professional.getProfessionalPatients('', 1, signal)).total > 0);
    assert.ok((await professional.getProfessionalProfile(signal)).specialty);
    assert.equal((await professional.getProfessionalHistory(fixture.account.id, 1, signal)).appointments[0].status, 'cancelled');
  });
  await t.test('weekly agenda loads every API page with date filters and includes historical appointments', async () => {
    const adapter = api.defaults.adapter;
    const requests = [];
    api.defaults.adapter = async config => {
      requests.push(config.params);
      const count = config.params.page === 1 ? 100 : 1;
      const appointments = Array.from({ length: count }, (_, index) => ({ id: `${config.params.page}-${index}`, start_time: '2026-11-03T09:30:00Z', end_time: '2026-11-03T10:00:00Z', status: 'completed' }));
      return { data: { appointments, total: 101, page: config.params.page, page_size: 100 }, status: 200, statusText: 'OK', headers: {}, config };
    };
    try {
      const rows = await professional.getProfessionalWeek('2026-11-02', '2026-11-08', new AbortController().signal);
      assert.equal(rows.length, 101);
      assert.deepEqual(requests.map(item => item.page), [1, 2]);
      assert.ok(requests.every(item => item.upcoming_only === false && item.from_date === '2026-11-02' && item.to_date === '2026-11-08' && item.page_size === 100));
    } finally { api.defaults.adapter = adapter; }
  });
  await t.test('weekly agenda fails instead of silently showing an incomplete week', async () => {
    const adapter = api.defaults.adapter;
    api.defaults.adapter = async config => ({ data: { appointments: [], total: 1, page: config.params.page, page_size: 100 }, status: 200, statusText: 'OK', headers: {}, config });
    try { await assert.rejects(professional.getProfessionalWeek('2026-11-02', '2026-11-08', new AbortController().signal)); }
    finally { api.defaults.adapter = adapter; }
  });
  await t.test('video entry starts from automatically confirmed bookings and preserves date-based reload lookup', async () => {
    fixture.state.videoTestAppointment = { id: '00000000-0000-4000-8000-000000000990', patient_id: fixture.participants.patient.id, patient_name: 'Paciente de videoconsulta', patient_username: 'video_fixture', professional_id: fixture.account.id, type: 'video', status: 'confirmed', start_time: '2030-11-04T10:00:00Z', end_time: '2030-11-04T10:30:00Z', appointment_reason: 'Consulta de prueba', cancellation_reason: null };
    const id = fixture.state.videoTestAppointment.id, signal = new AbortController().signal;
    assert.equal((await consultations.findVideoAppointment(id, '2030-11-04', signal)).status, 'confirmed');
    const joined = await consultations.joinVideo(id, signal);
    assert.equal(joined.domain, 'jitsi.fixture.invalid');
    assert.ok(Date.parse(joined.expires_at) > Date.now());
    fixture.state.videoDenied = true;
    await assert.rejects(consultations.joinVideo(id, signal), error => /horario/.test(consultations.consultationError(error)));
    assert.equal(fixture.state.videoTestAppointment.status, 'confirmed');
    fixture.state.videoDenied = false;
  });
  await t.test('native chat protocol broadcasts persisted messages and completed chat becomes read-only', async () => {
    const id = fixture.state.videoTestAppointment.id, signal = new AbortController().signal;
    assert.equal((await consultations.getChatRoom(id, signal)).can_write, true);
    const url = consultations.chatSocketUrl(id, session.read().access_token);
    assert.equal(new URL(url).protocol, 'ws:');
    const socket = new WebSocket(url);
    await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
    try {
      const receive = new Promise((resolve, reject) => { const timer = setTimeout(() => reject(new Error('Chat fixture timeout')), 2000); socket.addEventListener('message', event => { clearTimeout(timer); resolve(JSON.parse(String(event.data))); }, { once: true }); });
      socket.send(JSON.stringify({ type: 'message', content: 'Mensaje de prueba' }));
      const result = await receive;
      assert.equal(result.type, 'message'); assert.equal(result.content, 'Mensaje de prueba');
      const rows = await consultations.getChatMessages(id, signal);
      assert.equal(rows.at(-1).id, result.id);
    } finally { socket.close(); }
    await consultations.updateConsultationStatus(fixture.account.id, id, 'completed', signal);
    assert.equal((await consultations.getChatRoom(id, signal)).can_write, false);
  });
  await t.test('Jitsi origins reject unexpected protocols, credentials and paths', () => {
    assert.equal(jitsiOrigin('localhost:8443').origin, 'https://localhost:8443');
    assert.throws(() => jitsiOrigin('http://video.example.invalid'));
    assert.throws(() => jitsiOrigin('https://video.example.invalid/other'));
    assert.throws(() => jitsiOrigin('https://user:password@video.example.invalid'));
  });
});
