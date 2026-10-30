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
  for (const name of ['client', 'session', 'auth', 'notifications', 'errors', 'admin', 'adminUserErrors']) {
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
});
