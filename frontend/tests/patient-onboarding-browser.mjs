import assert from 'node:assert/strict';
import { checkPatientHealthProfile } from './patient-health-profile-browser.mjs';

export async function checkPatientOnboarding({ fixture, evaluate, click, fill, until, command, screenshot, checkGeometry, results, reloadUntil }) {
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: `${await evaluate('location.origin')}/patientPanel/onboarding/listo` });
  await until(`document.querySelector('.onboarding-actions .primary')?.textContent.includes('acepto')`);
  assert.equal(await evaluate('location.pathname'), '/patientPanel/onboarding');
  assert.equal(await evaluate(`document.querySelector('.site-header') === null`), true);
  assert.equal(fixture.state.onboardingAnswers, undefined);
  assert.equal(await evaluate(`document.querySelector('.onboarding-composer') === null`), true);
  assert.equal(await evaluate(`document.querySelector('.patient-brand img').getAttribute('src') === document.querySelector('.onboarding-avatar').getAttribute('src')`), true);
  await screenshot('patient-onboarding-consent');
  await click('.onboarding-actions .secondary');
  await until(`document.querySelector('.onboarding-stream').textContent.includes('no te haremos las preguntas')`);
  assert.equal(fixture.state.onboardingAnswers, undefined);
  await reloadUntil(`document.querySelector('.onboarding-stream')?.textContent.includes('no te haremos las preguntas')`);
  await click('.onboarding-actions .secondary');
  await until(`document.querySelector('.onboarding-composer') !== null`);
  assert.equal(await evaluate(`document.querySelector('.onboarding-stream').textContent.includes('en un solo mensaje')`), true);
  fixture.state.onboardingFail = true;
  await fill('onboarding-answer', 'No tengo alergias');
  await click('.onboarding-composer button');
  await until(`document.querySelector('.onboarding-error') !== null`);
  assert.equal(await evaluate(`document.querySelector('[name="onboarding-answer"]').value`), 'No tengo alergias');
  assert.equal(fixture.state.onboardingSaves, undefined);
  fixture.state.onboardingFail = false;
  await evaluate(`document.querySelector('.onboarding-composer').requestSubmit(); document.querySelector('.onboarding-composer').requestSubmit()`);
  await until(`document.querySelector('.onboarding-confirmation') !== null`);
  assert.equal(fixture.state.onboardingAnswers, 2); // failed request + one successful request
  assert.equal(fixture.state.onboardingSaves, undefined);
  await reloadUntil(`document.querySelector('.onboarding-confirmation') !== null`);
  await click('.onboarding-confirmation .secondary');
  await until(`document.querySelector('.onboarding-composer') !== null`);
  assert.equal(fixture.state.onboardingSaves, undefined);
  await fill('onboarding-answer', 'Alergia al polen, leve');
  await click('.onboarding-composer button');
  await until(`document.querySelector('.onboarding-confirmation')?.textContent.includes('polen')`);
  await until(`Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)`);
  results.push({ check: 'onboarding consent/decline persistence, no questions without consent, one-message guidance, provider retry, no save before OK, correction and resume', assets: await checkGeometry() });
  await screenshot('patient-onboarding-confirmation-desktop');
  await command('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  await evaluate(`document.querySelector('.onboarding-confirmation').scrollIntoView({ block: 'center' })`);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true);
  await screenshot('patient-onboarding-confirmation-mobile');
  await evaluate(`document.querySelector('.onboarding-confirmation .primary').click(); document.querySelector('.onboarding-confirmation .primary').click()`);
  await until(`document.querySelector('.onboarding-composer') !== null`);
  assert.equal(fixture.state.onboardingSaves, 1);
  // Complete every remaining question through its own confirmation boundary.
  while (fixture.state.onboarding.stage !== 'completed') {
    await fill('onboarding-answer', fixture.state.onboarding.question.id === 'height' ? '178 cm' : 'Respuesta sintética de prueba');
    const before = fixture.state.onboardingSaves;
    await click('.onboarding-composer button');
    await until(`document.querySelector('.onboarding-confirmation') !== null`);
    assert.equal(fixture.state.onboardingSaves, before);
    await click('.onboarding-confirmation .primary');
    await until(`document.querySelector('.onboarding-confirmation') === null`);
  }
  await until(`location.pathname === '/patientPanel/onboarding/listo' && document.querySelector('.health-complete-card h1')?.textContent === 'Tu perfil de salud está listo'`);
  assert.equal(fixture.state.onboardingSaves, 13);
  await reloadUntil(`document.querySelector('.health-complete-card h1')?.textContent === 'Tu perfil de salud está listo'`);
  await screenshot('patient-onboarding-complete-mobile');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  await screenshot('patient-onboarding-complete-desktop');
  await click('.health-complete-card .primary');
  await checkPatientHealthProfile({ fixture, evaluate, click, fill, until, command, screenshot, checkGeometry, results, reloadUntil });
  results.push({ check: 'onboarding mobile geometry, duplicate OK protection, all 13 questions individually confirmed, completion survives reload' });
  await command('Page.navigate', { url: `${await evaluate('location.origin')}/patientPanel` });
  await until(`document.querySelector('.patient-greeting') !== null`);
}
