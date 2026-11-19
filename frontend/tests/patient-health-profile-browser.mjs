import assert from 'node:assert/strict';

export async function checkPatientHealthProfile({ fixture, evaluate, click, fill, until, command, screenshot, checkGeometry, results, reloadUntil }) {
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  await until(`document.querySelector('#health-allergies h3')?.textContent.includes('Polen')`);
  assert.equal(await evaluate(`document.querySelector('.site-header') === null`), true);
  assert.equal(await evaluate(`document.querySelectorAll('.health-section button, .health-section input, .health-section select').length`), 0);
  assert.equal(await evaluate(`document.querySelector('#health-biometrics').textContent.includes('178')`), true);
  assert.equal(await evaluate(`document.querySelector('#health-biometrics').textContent.includes('Grupo sanguíneo')`), false);
  assert.equal(await evaluate(`document.querySelector('.health-profile-main').textContent.includes('Presión Arterial') || document.querySelector('.health-profile-main').textContent.includes('Descargar Expediente')`), false);
  await until(`Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)`);
  results.push({ check: 'saved profile is read-only: no per-section edit/add controls, existing measurements and unknown values rendered correctly', assets: await checkGeometry() });
  await screenshot('patient-health-profile-desktop');
  fixture.state.omitAppointmentFollowUps = true;
  await reloadUntil(`document.querySelector('#health-appointment-follow-ups .health-empty')?.textContent.includes('no está disponible')`);
  assert.equal(await evaluate(`document.querySelector('#health-allergies h3')?.textContent.includes('Polen')`), true);
  fixture.state.omitAppointmentFollowUps = false;
  await reloadUntil(`document.querySelector('#health-appointment-follow-ups .health-empty')?.textContent.includes('Aún no hay')`);
  results.push({ check: 'profile still renders when the API omits appointment follow-ups' });
  await click('.health-consent:last-of-type button');
  await until(`document.querySelector('.health-consent:last-of-type button')?.textContent.includes('Revocar consentimiento')`);
  assert.equal(fixture.state.shareHealthData, true);
  await click('.health-consent:last-of-type button');
  await until(`document.querySelector('.health-consent:last-of-type button')?.textContent.includes('Activar consentimiento')`);
  assert.equal(fixture.state.shareHealthData, false);
  results.push({ check: 'patient can activate and revoke global profile sharing from the health profile' });
  await click('.health-sharing-professionals summary');
  await until(`document.querySelectorAll('.health-sharing-list li').length === 2`);
  assert.equal(await evaluate(`document.querySelector('.health-sharing-list li').textContent.includes('Acceso suspendido')`), true);
  await click('.health-sharing-list button[aria-label="Revocar acceso de Profesional A"]');
  await click('.health-sharing-list li:first-child button.button');
  await until(`document.querySelectorAll('.health-sharing-list li').length === 1`);
  assert.equal(fixture.state.sharingPermissions[0].professional_name, 'Profesional B');
  results.push({ check: 'patient can review and revoke a single professional permission while global access is suspended' });
  const clinical = () => JSON.stringify({ profile: fixture.state.healthProfile.profile, allergies: fixture.state.healthProfile.allergies, medications: fixture.state.healthProfile.medications, conditions: fixture.state.healthProfile.chronic_conditions, family: fixture.state.healthProfile.family_history_entries, habits: fixture.state.healthProfile.habit_logs, alcohol: fixture.state.healthProfile.alcohol_logs });
  const before = clinical();
  const saves = fixture.state.onboardingSaves;
  const calls = fixture.state.onboardingAnswers;
  await evaluate(`document.querySelector('.health-open-assistant').click(); document.querySelector('.health-open-assistant').click()`);
  await until(`location.pathname === '/patientPanel/onboarding' && document.querySelector('.onboarding-skip button') !== null`);
  assert.equal(clinical(), before);
  assert.equal(fixture.state.onboarding.completed_questions, 0);
  while (fixture.state.onboarding.stage !== 'completed') {
    const question = fixture.state.onboarding.question.id;
    if (question === 'weight') {
      await fill('onboarding-answer', '80 kg');
      await click('.onboarding-composer button');
      await until(`document.querySelector('.onboarding-confirmation') !== null`);
      assert.equal(fixture.state.healthProfile.profile.weight_kg, 74);
      await click('.onboarding-confirmation .primary');
      await until(`document.querySelector('.onboarding-confirmation') === null`);
    } else {
      const prior = fixture.state.onboarding.completed_questions;
      await evaluate(`document.querySelector('.onboarding-skip button').click(); document.querySelector('.onboarding-skip button').click()`);
      await until(`document.querySelector('.health-complete-card') !== null || document.querySelector('.onboarding-skip button:not([disabled])') !== null`);
      assert.equal(fixture.state.onboarding.completed_questions, prior + 1);
      if (question === 'height') {
        await reloadUntil(`document.querySelector('.onboarding-skip button') !== null`);
        assert.ok(fixture.state.onboarding.skipped_questions.includes('height'));
      }
    }
  }
  await until(`document.querySelector('.health-complete-card h1')?.textContent === 'Tu perfil de salud está listo'`);
  assert.equal(fixture.state.onboardingSaves, saves + 1);
  assert.equal(fixture.state.onboardingAnswers, calls + 1);
  assert.equal(fixture.state.healthProfile.profile.height_cm, 178);
  assert.equal(fixture.state.healthProfile.profile.blood_type, null);
  assert.equal(fixture.state.healthProfile.habit_logs.length, 1);
  assert.equal(fixture.state.healthProfile.allergies[0].name, 'Polen de gramíneas');
  await click('.health-complete-card .primary');
  await until(`document.querySelector('#health-biometrics')?.textContent.includes('80')`);
  await reloadUntil(`document.querySelector('#health-biometrics')?.textContent.includes('80')`);
  assert.equal(fixture.state.healthProfileWrites, undefined);
  results.push({ check: 'profile opens a new AI update cycle, skip preserves existing/empty fields without AI calls, only answered weight saves after confirmation, duplicate skip and reload protection' });

  // A full pass with nothing changed must be a clinical no-op.
  const unchanged = clinical();
  const unchangedSaves = fixture.state.onboardingSaves;
  await click('.health-open-assistant');
  await until(`document.querySelector('.onboarding-skip button:not([disabled])') !== null`);
  while (fixture.state.onboarding.stage !== 'completed') {
    await click('.onboarding-skip button');
    await until(`document.querySelector('.health-complete-card') !== null || document.querySelector('.onboarding-skip button:not([disabled])') !== null`);
  }
  await until(`document.querySelector('.health-complete-card') !== null`);
  assert.equal(clinical(), unchanged);
  assert.equal(fixture.state.onboardingSaves, unchangedSaves);
  await click('.health-complete-card .primary');
  await until(`document.querySelector('#health-biometrics') !== null`);
  fixture.state.healthProfile.profile.height_cm = null;
  await reloadUntil(`document.querySelector('.health-bmi-missing')?.textContent.includes('No se puede calcular el BMI')`);
  await command('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true);
  await screenshot('patient-health-profile-mobile');
  fixture.state.healthProfileFail = true;
  await reloadUntil(`document.querySelector('.health-profile-main [role="alert"]') !== null`);
  fixture.state.healthProfileFail = false;
  await click('.health-profile-main [role="alert"] button');
  await until(`document.querySelector('.health-bmi-missing') !== null`);
  results.push({ check: 'all-skipped update leaves clinical data unchanged, missing height shows BMI explanation, mobile geometry and retry' });
}
