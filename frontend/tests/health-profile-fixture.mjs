// Synthetic saved health records used only by the browser tests.
export function healthProfileFixture(path, method, raw, state, send) {
  if (!path.startsWith('/patients/me/health-profile')) return false;
  if (method !== 'GET') { send(404, { detail: 'PROFILE_IS_READ_ONLY' }); return true; }
  if (state.healthProfileFail) { send(503, { detail: 'TEST_UNAVAILABLE' }); return true; }
  const data = state.healthProfile ??= {
    profile: { id: '00000000-0000-4000-8000-000000009001', user_id: '00000000-0000-4000-8000-000000000001', height_cm: 178, weight_kg: 74, blood_type: null, timezone: 'Europe/Madrid', onboarding_completed: true, share_health_data: false, ai_processing_consent: true, ai_processing_consent_at: '2026-11-16T10:00:00Z' },
    allergies: [{ id: 1, name: 'Polen de gramíneas', severity: 'leve' }],
    medications: [{ id: 2, name: 'Medicamento sintético', dosage: '10 mg', frequency: 'Una vez al día', active: true }],
    chronic_conditions: [], family_history_entries: [{ id: 3, relationship: 'madre', condition_category: 'diabetes', detail: 'Dato familiar de prueba', age_at_diagnosis: null, recorded_date: '2026-11-16' }],
    habit_logs: [{ id: 4, habit_type: 'ejercicio', value: 150, unit: 'min/semana', date: '2026-11-16' }],
    alcohol_logs: [{ id: 5, frequency: 0, quantity: null, binge: null, date: '2026-11-16' }],
    declarations: { chronic_conditions: 'none', sleep: 'unknown' }, onboarding_stage: 'completed',
  };
  data.onboarding_stage = state.onboarding?.stage ?? data.onboarding_stage;
  send(200, data);
  return true;
}
