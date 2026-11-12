import assert from 'node:assert/strict';

// Called by the existing Chrome harness with a synthetic authenticated patient.
export async function checkPatientDashboard({ fixture, evaluate, click, until, command, screenshot, checkGeometry, results, reloadUntil }) {
  await until(`document.querySelector('.patient-consent-check') !== null`);
  assert.equal(await evaluate(`document.querySelector('.patient-empty .primary').disabled`), true);
  assert.equal(await evaluate(`document.querySelectorAll('.patient-risk-card').length`), 0);
  assert.equal(fixture.state.patientConsentWrites, undefined);
  await click('.patient-consent-check input');
  await evaluate(`document.querySelector('.patient-empty .primary').click(); document.querySelector('.patient-empty .primary').click()`);
  await until(`document.querySelectorAll('.patient-risk-card').length === 4`);
  assert.equal(fixture.state.patientConsentWrites, 1);
  assert.ok(fixture.state.patientRiskPaths.every(path => path.includes('000000009001')));
  assert.equal(await evaluate(`document.querySelector('.patient-risk-card').textContent.includes('Datos insuficientes')`), true);
  assert.equal(await evaluate(`document.body.textContent.includes('CLÍNICA PRINCIPAL') || document.body.textContent.includes('SALUD METABÓLICA')`), false);
  results.push({ check: 'patient dashboard explicit consent, duplicate prevention, profile ID distinct from account and insufficient/unavailable evaluations' });

  fixture.state.patientDashboardAppointments = Array.from({ length: 101 }, (_, index) => ({
    id: `appointment-test-${index}`, professional_id: fixture.participants.professional.id,
    professional_name: index === 100 ? 'Profesional de la próxima cita' : 'Profesional de prueba',
    type: 'video', status: 'confirmed', appointment_reason: null,
    start_time: new Date(Date.now() + (index === 100 ? 5 : 1440 + index) * 60000).toISOString(),
    end_time: new Date(Date.now() + (index === 100 ? 35 : 1470 + index) * 60000).toISOString(),
  }));
  fixture.state.patientRisks = [
    { model: 'bmi', status: 'ok', metric_value: 23.5, category: 'healthy', alert_level: 'info', missing: [], trend: 'stable', explanation: 'Test', source: 'Test', disclaimer: 'Test' },
    { model: 'tobacco', status: 'error', metric_value: null, category: null, alert_level: null, missing: [], trend: 'insufficient_history', explanation: 'Test', source: 'Test', disclaimer: 'Test' },
    { model: 'family_diabetes', status: 'ok', metric_value: 1, category: 'family_history', alert_level: 'elevated', missing: [], trend: 'insufficient_history', explanation: 'Test', source: 'Test', disclaimer: 'Test' },
  ];
  await reloadUntil(`document.querySelector('.patient-next-content')?.textContent.includes('Profesional de la próxima cita') && document.querySelectorAll('.patient-risk-card').length === 5`);
  assert.ok(fixture.state.patientDashboardPages.includes(2));
  assert.equal(await evaluate(`document.querySelector('.patient-next-content .primary').getAttribute('href')`), '/patientPanel/videoconsulta/appointment-test-100');
  assert.equal(await evaluate(`document.querySelector('.patient-risk-value').textContent`), '23,5 kg/m²');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  await until(`Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)`);
  results.push({ check: 'patient dashboard chooses nearest appointment on second page, real value/error/family cards and desktop assets', assets: await checkGeometry() });
  await screenshot('patient-dashboard-desktop');

  await click('.patient-risk-card .text-button');
  await until(`document.querySelector('dialog')?.textContent.includes('No hay evaluaciones guardadas')`);
  assert.equal(await evaluate(`document.querySelector('dialog').contains(document.activeElement)`), true);
  await command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await until(`document.querySelector('dialog') === null`);
  await click('.patient-quick-actions button:nth-child(2)');
  await until(`document.querySelector('dialog')?.textContent.includes('No hay hábitos registrados')`);
  await click('dialog .modal-heading button');
  fixture.state.patientRiskFail = true;
  await click('#evaluaciones .patient-section-heading button');
  await until(`document.querySelector('#evaluaciones [role="alert"]') !== null`);
  fixture.state.patientRiskFail = false;
  await click('#evaluaciones [role="alert"] button');
  await until(`document.querySelectorAll('.patient-risk-card').length === 5`);
  results.push({ check: 'patient history and habits empty states, native dialog focus/Escape, risk request error and retry' });

  await click('.patient-quick-actions button:first-child');
  await until(`document.querySelector('input[type="file"]') !== null`);
  await evaluate(`(() => { const transfer = new DataTransfer(); transfer.items.add(new File(['%PDF-1.4 synthetic'], 'test.pdf', { type: 'application/pdf' })); const input = document.querySelector('input[type="file"]'); input.files = transfer.files; input.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  fixture.state.patientUploadFail = true;
  await click('dialog button[type="submit"]');
  await until(`document.querySelector('dialog [role="alert"]') !== null`);
  assert.equal(await evaluate(`document.querySelector('dialog [role="alert"]').textContent`), 'El archivo debe ser PDF, JPEG o PNG.');
  fixture.state.patientUploadFail = false;
  await evaluate(`document.querySelector('dialog form').requestSubmit(); document.querySelector('dialog form').requestSubmit()`);
  await until(`document.querySelector('dialog [role="status"]')?.textContent.includes('subido correctamente')`);
  assert.equal(fixture.state.patientUploadCalls, 2);
  assert.equal(fixture.state.patientUploadMultipart, true);
  await click('dialog .modal-heading button');
  results.push({ check: 'patient document multipart upload, server validation, retry and duplicate submission protection' });

  await command('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  results.push({ check: 'patient dashboard mobile geometry and SVG root dimensions', assets: await checkGeometry() });
  await screenshot('patient-dashboard-mobile');
  await click('.patient-menu-button');
  await until(`document.querySelector('.patient-sidebar.is-open') !== null`);
  await click('.patient-sidebar nav button');
  await until(`document.querySelector('dialog')?.textContent.includes('Sin registrar')`);
  await click('dialog .modal-heading button');
  await until(`document.querySelector('.patient-sidebar.is-open') === null`);
  fixture.state.patientDashboardAppointments = undefined;
  results.push({ check: 'patient mobile navigation opens profile with missing optional fields and closes after selection' });
}
