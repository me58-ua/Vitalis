import assert from 'node:assert/strict';

export async function checkPatientPrescriptions({ fixture, evaluate, click, until, command, screenshot, checkGeometry, results, reloadUntil }) {
  const day = offset => {
    const parts = new Intl.DateTimeFormat('en', { timeZone: 'Europe/Madrid', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
    const get = key => parts.find(item => item.type === key).value;
    return new Date(Date.parse(`${get('year')}-${get('month')}-${get('day')}T12:00:00Z`) + offset * 86400000).toISOString().slice(0, 10);
  };
  const recipe = (id, changes) => ({ id: `recipe-${id}`, appointment_id: `appointment-${id}`, patient_id: 'profile-only', professional_id: 'professional-profile', professional_name: 'Dra. Elena de prueba', appointment_date: '2026-11-01T10:00:00Z', appointment_reason: 'Revisión de prueba', file_url: 'prescriptions/test.pdf', download_url: `/patients/me/appointments/appointment-${id}/prescription`, notas: null, created_at: '2026-11-01T10:00:00Z', tipo: 'medicacion', titulo: 'Atorvastatina y Metformina', fecha_emision: day(-30), fecha_caducidad: day(30), codigo: 'EXT-123', ...changes });
  fixture.state.myPrescriptions = [
    recipe(1, {}), recipe(2, { titulo: 'Solicitud de analítica', tipo: 'prueba', fecha_caducidad: day(7), codigo: null }),
    recipe(3, { titulo: 'Documento vencido', fecha_caducidad: day(-1) }),
    recipe(4, { titulo: null, tipo: null, fecha_emision: null, fecha_caducidad: null, codigo: null }),
  ];
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: `${await evaluate('location.origin')}/patientPanel/misRecetas` });
  await until(`document.querySelectorAll('.patient-prescription-card').length === 4 && Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)`);
  assert.equal(await evaluate(`document.querySelector('.patient-sidebar [aria-current="page"]').textContent`), 'Mis recetas');
  assert.equal(await evaluate(`document.querySelector('.recipe-expiry-banner').textContent.includes('Expira en 7 días'.toLowerCase())`), true);
  assert.equal(await evaluate(`document.querySelector('.validity-unknown').textContent.includes('Vigencia no indicada')`), true);
  assert.equal(await evaluate(`document.querySelectorAll('.patient-prescription-card button').length`), 4);
  assert.ok(fixture.state.patientPrescriptionPaths.every(value => !value.includes('000000009001')));
  results.push({ check: 'prescription desktop cards, confirmed dates, test requests, legacy metadata, expiry banner and local Figma icons', assets: await checkGeometry() });
  await screenshot('patient-prescriptions-desktop');
  await click('.recipe-status-filters button:nth-child(3)');
  await until(`document.querySelectorAll('.patient-prescription-card').length === 1`);
  assert.equal(await evaluate(`document.querySelector('.patient-prescription-card h2').textContent`), 'Solicitud de analítica');
  await click('.recipe-status-filters button:first-child');
  await evaluate(`(() => { const input = document.querySelector('.recipe-search-filters input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'EXT-123'); input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
  await until(`document.querySelectorAll('.patient-prescription-card').length === 2`);
  await evaluate(`(() => { const input = document.querySelector('.recipe-search-filters input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'no-match'); input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
  await until(`document.querySelector('.patient-empty h2')?.textContent.includes('filtros')`);
  await click('.patient-empty button');
  await until(`document.querySelectorAll('.patient-prescription-card').length === 4`);
  await evaluate(`(() => { const select = document.querySelector('.recipe-search-filters select'); select.value = 'prueba'; select.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  await until(`document.querySelectorAll('.patient-prescription-card').length === 1`);
  fixture.state.patientPrescriptionDownloadFail = true;
  await click('.recipe-card-actions button');
  await until(`document.querySelector('.patient-prescription-card [role="alert"]') !== null`);
  fixture.state.patientPrescriptionDownloadFail = false;
  await evaluate(`document.querySelector('.recipe-card-actions button').click(); document.querySelector('.recipe-card-actions button').click()`);
  await until(`document.querySelector('.recipe-card-actions button:not(:disabled)') !== null && document.querySelector('.patient-prescription-card [role="alert"]') === null`);
  assert.equal(fixture.state.patientPrescriptionDownloads, 1);
  results.push({ check: 'prescription status/code/type search, no-match state, authenticated download retry and duplicate prevention' });
  await command('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  await until(`Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)`);
  results.push({ check: 'prescription mobile layout and SVG dimensions', assets: await checkGeometry() });
  await screenshot('patient-prescriptions-mobile');
  fixture.state.patientPrescriptionsFail = true;
  await reloadUntil(`document.querySelector('.patient-prescriptions-main [role="alert"]') !== null`);
  fixture.state.patientPrescriptionsFail = false;
  await click('.patient-prescriptions-main [role="alert"] button');
  await until(`document.querySelectorAll('.patient-prescription-card').length === 4`);
  fixture.state.myPrescriptions = [];
  await reloadUntil(`document.querySelector('.patient-empty h2')?.textContent.includes('Todavía')`);
  assert.equal(await evaluate(`document.querySelector('.recipe-expiry-banner') === null`), true);
  results.push({ check: 'prescription request failure/retry, empty list, direct route restoration' });
  await command('Page.navigate', { url: `${await evaluate('location.origin')}/patientPanel` });
  await until(`document.querySelector('.patient-greeting') !== null`);
}
