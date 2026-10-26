// Run explicitly: node tests/browser-smoke.mjs. Uses installed Chrome, no browser library.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { fixtureServer } from './fixture-server.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'test-results');
await mkdir(output, { recursive: true });
const fixture = await fixtureServer();
const vite = await createServer({
  root, configFile: path.join(root, 'vite.config.ts'),
  define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify(fixture.url) },
  server: { host: 'localhost', port: 3000, strictPort: true },
});
let browser;
let socket;
const pending = new Map();
let serial = 0;
let targetSession;
const runtimeErrors = [];
const results = [];
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

try {
  await vite.listen();
  const chrome = process.env.VITALIS_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  if (!existsSync(chrome)) throw new Error('Set VITALIS_BROWSER to the installed Chrome executable.');
  const profile = path.join(output, `chrome-${process.pid}`);
  browser = spawn(chrome, [
    '--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-gpu',
    '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
  ], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
  const endpoint = await new Promise((resolve, reject) => {
    let buffer = '';
    const timeout = setTimeout(() => reject(new Error('Chrome startup timed out')), 20000);
    browser.on('error', reject);
    browser.stderr.on('data', (part) => {
      buffer += String(part);
      const match = buffer.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) { clearTimeout(timeout); resolve(match[1]); }
    });
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(String(event.data));
    if (message.method === 'Runtime.exceptionThrown') runtimeErrors.push(message.params.exceptionDetails.text);
    const waiter = pending.get(message.id);
    if (waiter) {
      pending.delete(message.id); clearTimeout(waiter.timeout);
      if (message.error) waiter.reject(new Error(message.error.message));
      else waiter.resolve(message.result);
    }
  });
  function command(method, params = {}, sessionId = targetSession) {
    return new Promise((resolve, reject) => {
      const id = ++serial;
      const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
      pending.set(id, { resolve, reject, timeout });
      socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }
  async function evaluate(expression) {
    const response = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description || response.exceptionDetails.text);
    return response.result.value;
  }
  async function until(expression) {
    for (let i = 0; i < 100; i += 1) { if (await evaluate(expression)) return; await sleep(100); }
    throw new Error(`Browser condition timed out: ${expression}`);
  }
  async function click(selector) {
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  }
  async function fill(name, value) {
    await evaluate(`(() => {
      const input = document.querySelector('[name="${name}"]');
      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set.call(input, ${JSON.stringify(value)});
      input.dispatchEvent(new Event('input', { bubbles: true }));
    })()`);
  }
  async function screenshot(name, full = true) {
    const { cssContentSize } = await command('Page.getLayoutMetrics');
    const shot = await command('Page.captureScreenshot', {
      format: 'png', captureBeyondViewport: true,
      ...(full ? { clip: { x: 0, y: 0, width: cssContentSize.width, height: cssContentSize.height, scale: 1 } } : {}),
    });
    await writeFile(path.join(output, `${name}.png`), Buffer.from(shot.data, 'base64'));
  }
  async function checkGeometry() {
    assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true, 'horizontal overflow');
    const assets = await evaluate(`Array.from(document.images).filter(img => img.getClientRects().length).map(img => ({ src: img.getAttribute('src'), natural: img.naturalWidth, width: img.getBoundingClientRect().width, height: img.getBoundingClientRect().height }))`);
    assert.ok(assets.every((item) => item.natural > 0 && item.width > 0 && item.height > 0));
    assert.ok(assets.every((item) => !item.src.startsWith('https://www.figma.com')));
    const roots = await evaluate(`Array.from(document.images).filter(img => img.getClientRects().length && img.currentSrc.endsWith('.svg')).map(img => ({ src: img.currentSrc, width: img.getBoundingClientRect().width, height: img.getBoundingClientRect().height }))`);
    for (const asset of roots) {
      const file = new URL(asset.src).pathname.split('/').at(-1);
      const svg = await readFile(path.join(root, new URL(asset.src).pathname.slice(1)), 'utf8');
      assert.ok(Math.abs(Number(svg.match(/width="([\d.]+)"/)[1]) - asset.width) < 1, `SVG width: ${file}`);
      assert.ok(Math.abs(Number(svg.match(/height="([\d.]+)"/)[1]) - asset.height) < 1, `SVG height: ${file}`);
    }
    return assets.length;
  }
  const { targetId } = await command('Target.createTarget', { url: 'about:blank' }, null);
  targetSession = (await command('Target.attachToTarget', { targetId, flatten: true }, null)).sessionId;
  await command('Page.enable'); await command('Runtime.enable');
  const downloadPath = path.join(output, 'downloads');
  await mkdir(downloadPath, { recursive: true });
  await command('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath }, null);
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: 'http://localhost:3000' });
  await until(`document.querySelector('.hero-photo') && Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)`);
  results.push({ check: 'desktop geometry and local assets', assets: await checkGeometry() });
  await screenshot('homepage-desktop');
  await command('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  await sleep(100);
  results.push({ check: 'mobile geometry and SVG dimensions', assets: await checkGeometry() });
  await screenshot('homepage-mobile');
  await click('.hero-actions .primary');
  await until(`document.querySelector('dialog[open]') !== null`);
  assert.equal(await evaluate(`document.querySelector('dialog').contains(document.activeElement)`), true, 'dialog initial focus');
  await command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await until(`document.querySelector('dialog') === null`);
  results.push({ check: 'native dialog focus and Escape' });
  await click('.hero-actions .secondary');
  await until(`document.querySelector('[name="confirm_password"]') !== null`);
  for (const [name, value] of Object.entries({ name: 'Registro sintético', dni: 'TEST-12345', username: 'test_professional', email: 'professional@example.invalid', tel: '000000000', birth_date: '1980-01-01', password: 'TestPassword!', confirm_password: 'TestPassword!' })) await fill(name, value);
  await click('button[type="submit"]');
  await until(`document.querySelector('[name="specialty"]') !== null`);
  for (const [name, value] of Object.entries({ specialty: 'Pruebas', license_number: 'TEST-COL', bio: 'Cuenta exclusiva de pruebas', practice_address: 'Test address', practice_phone: '000000000', duration: '30' })) await fill(name, value);
  await click('[name="terms_accepted"]');
  await click('button[type="submit"]');
  await until(`document.querySelector('.success-state') !== null`);
  assert.equal(fixture.state.registrations.length, 1);
  assert.equal(fixture.state.registrations[0].role, 'professional');
  assert.equal(fixture.state.registrations[0].telehealth_enabled, false);
  results.push({ check: 'professional registration schema and approval notice' });
  await click('.success-state button');
  await until(`document.querySelector('[name="identifier"]') !== null`);
  await until(`location.pathname === '/login' && !document.querySelector('dialog')`);
  results.push({ check: 'login mobile geometry and local icons', assets: await checkGeometry() });
  await screenshot('login-mobile');
  assert.equal(await evaluate(`Array.from(document.querySelectorAll('a,button')).filter(el => el.textContent.includes('Crear cuenta')).length`), 1);
  await click('.login-registration button');
  await until(`document.querySelector('dialog[open]') !== null`);
  await click('[name="role"][value="professional"]');
  assert.equal(await evaluate(`document.querySelector('[name="role"]:checked').value`), 'professional');
  await click('dialog .modal-heading button');
  await command('Emulation.setDeviceMetricsOverride', { width: 1280, height: 960, deviceScaleFactor: 1, mobile: false });
  results.push({ check: 'login desktop geometry and local icons', assets: await checkGeometry() });
  await screenshot('login-desktop');
  const beforeEmpty = fixture.state.logins;
  await click('button[type="submit"]');
  assert.equal(fixture.state.logins, beforeEmpty);
  await fill('identifier', 'test_user'); await fill('password', 'incorrect');
  await click('.login-visibility');
  assert.equal(await evaluate(`document.querySelector('[name="password"]').type`), 'text');
  await click('.login-visibility');
  await click('button[type="submit"]');
  await until(`document.querySelector('form [role="alert"]') !== null`);
  await fill('password', 'TestPassword!');
  await click('button[type="submit"]');
  await until(`location.pathname === '/patientPanel' && document.querySelector('main h1')?.textContent === 'Página de paciente'`);
  results.push({ check: 'patient login redirects to patientPanel' });
  await click('.brand');
  await until(`document.querySelector('.signed-in-state') !== null`);
  results.push({ check: 'authenticated header geometry and local icons', assets: await checkGeometry() });
  await click('.notifications > button');
  await until(`document.querySelector('.notification-list li') !== null`);
  await click('.notification-list .text-button');
  await until(`document.querySelector('.notification-dot') === null`);
  assert.equal(fixture.state.reads, 1);
  results.push({ check: 'login error, authenticated account, notifications and marking read' });
  fixture.state.empty = true;
  await click('.notification-panel > .text-button');
  await until(`document.querySelector('.notification-panel').textContent.includes('No tienes notificaciones.')`);
  fixture.state.failNotifications = true;
  await click('.notification-panel > .text-button');
  await until(`document.querySelector('.notification-panel [role="alert"]') !== null`);
  fixture.state.failNotifications = false;
  await click('.notification-panel [role="alert"] button');
  await until(`!document.querySelector('.notification-panel [role="alert"]') && document.querySelector('.notification-panel').textContent.includes('No tienes notificaciones.')`);
  results.push({ check: 'notification empty, error and retry states' });
  await click('.notification-panel .icon-button');
  await click('.search-trigger');
  await until(`document.querySelector('[name="q"]') !== null`);
  await fill('q', 'informe');
  await click('.document-search-form button');
  await until(`document.querySelector('.document-results li') !== null`);
  await screenshot('document-search-mobile', false);
  await click('.document-results .text-button');
  await until(`document.querySelector('.document-results .text-button').textContent === 'Descargar'`);
  assert.equal(fixture.state.downloads, 1);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true);
  fixture.state.searchEmpty = true;
  await click('.document-search-form button');
  await until(`document.querySelector('dialog').textContent.includes('No se han encontrado documentos.')`);
  fixture.state.failSearch = true;
  await click('.document-search-form button');
  await until(`document.querySelector('dialog [role="alert"]') !== null`);
  fixture.state.failSearch = false;
  await click('dialog [role="alert"] button');
  await until(`!document.querySelector('dialog [role="alert"]') && document.querySelector('dialog').textContent.includes('No se han encontrado documentos.')`);
  await click('dialog .modal-heading button');
  results.push({ check: 'document search, authenticated download, empty, error, retry and mobile layout' });
  fixture.state.failLogout = true;
  await click('.account-menu summary'); await click('.account-panel button');
  await until(`document.querySelector('.account-panel [role="alert"]') !== null`);
  assert.equal(fixture.state.logouts, 0);
  assert.ok(await evaluate(`document.querySelector('.signed-in-state') !== null`));
  fixture.state.failLogout = false;
  await click('.account-panel button');
  await until(`document.querySelector('.signed-in-state') === null && document.querySelector('.notifications') === null`);
  assert.equal(await evaluate(`document.body.textContent.includes('Cuenta de pruebas')`), false);
  assert.equal(fixture.state.logouts, 1);
  results.push({ check: 'server logout error, retry and clearing account data after success' });
  fixture.account.role = 'professional';
  await click('.header-login');
  await until(`location.pathname === '/login'`);
  await fill('identifier', 'test_user'); await fill('password', 'TestPassword!');
  await click('button[type="submit"]');
  await until(`location.pathname === '/professionalDashboard' && document.querySelector('main h1')?.textContent === 'Página de profesional'`);
  // Exercise SPA navigation without losing the in-memory session.
  await evaluate(`history.pushState(null, '', '/patientPanel'); window.dispatchEvent(new PopStateEvent('popstate'))`);
  await until(`location.pathname === '/professionalDashboard'`);
  assert.equal(await evaluate(`document.querySelector('main h1').textContent`), 'Página de profesional');
  await evaluate(`history.pushState(null, '', '/login'); window.dispatchEvent(new PopStateEvent('popstate'))`);
  await until(`location.pathname === '/professionalDashboard'`);
  await command('Page.reload');
  await until(`location.pathname === '/login' && document.querySelector('[name="identifier"]') !== null`);
  await command('Page.navigate', { url: 'http://localhost:3000/patientPanel' });
  await until(`location.pathname === '/login' && document.querySelector('[name="identifier"]') !== null`);
  results.push({ check: 'professional destination, role guard, authenticated login redirect and reload session clearing' });
  assert.deepEqual(runtimeErrors, []);
  await writeFile(path.join(output, 'browser-report.json'), JSON.stringify({ results, runtimeErrors }, null, 2));
  console.log(JSON.stringify({ passed: results.length, results, runtimeErrors }, null, 2));
  await command('Browser.close', {}, null);
} finally {
  socket?.close();
  browser?.kill();
  await vite.close();
  await fixture.close();
}
