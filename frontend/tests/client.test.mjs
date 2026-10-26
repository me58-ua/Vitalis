import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import { fixtureServer } from './fixture-server.mjs';

test('Axios follows authentication and notification contracts', async (t) => {
  const fixture = await fixtureServer();
  t.after(fixture.close);
  const root = fileURLToPath(new URL('../', import.meta.url));
  const output = path.join(root, 'test-results', 'client');
  await mkdir(output, { recursive: true });
  for (const name of ['client', 'session', 'auth', 'notifications', 'errors']) {
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

  await t.test('URL-encoded login and account lookup', async () => {
    const tokens = await auth.login('test_user', 'TestPassword!');
    session.replace(tokens);
    assert.equal((await auth.currentUser()).id, fixture.account.id);
    assert.equal(tokens.token_type, 'bearer');
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
  });
});
