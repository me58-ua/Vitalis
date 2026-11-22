// Synthetic fixtures are restricted to test code. Never imported by src/.
import http from 'node:http';
import { createHash, randomUUID } from 'node:crypto';
import { onboardingFixture } from './onboarding-fixture.mjs';
import { healthProfileFixture } from './health-profile-fixture.mjs';

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
  Object.assign(state, { userManagement: false, failUsers: false, userFailure: null, userWrites: [], userQueries: [] });
  const managedUsers = [participants.patient, ...Array.from({ length: 20 }, (_, index) => ({ ...participants.patient,
    id: `00000000-0000-4000-8000-${String(601 + index).padStart(12, '0')}`, name: `Paciente de prueba ${index + 2}`, username: `patient_test_${index + 2}` })), participants.professional, account];
  const detailUser = item => ({ ...item, patient_profile: item.patient_profile ?? (item.role === 'patient' ? { address: null, blood_type: null, timezone: 'Europe/Madrid', sex_at_birth: null, height_cm: null, weight_kg: null } : null),
    professional_profile: state.profileByUser?.[item.id] ?? item.professional_profile ?? (item.role === 'professional' ? { specialty: 'Especialidad sintética', license_number: 'TEST-COL', bio: null, practice_address: null, practice_phone: null, is_accepting_new_patients: true, default_consultation_duration_minutes: 30, telehealth_enabled: true, approval_status: 'approved', rejection_reason: null, reviewed_at: null, reviewed_by: null, id: item.id, user_id: item.id } : null) });
  const demoSessions = [];
  state.timeBlocks = []; state.profileUpdates = []; state.profileByUser = {};
  state.workingHours = []; state.quickChats = []; state.quickMessages = []; state.quickAvailable = true; state.quickUploads = 0;
  const chatConnections = new Map();
  let broadcastSpontaneous = () => {};
  state.chatMessages = []; state.videoJoinCalls = 0; state.videoStatusWrites = [];
  const appointments = [0, 1].map(index => ({ id: `00000000-0000-4000-8000-${String(301 + index).padStart(12, '0')}`, patient_id: participants.patient.id, professional_id: participants.professional.id, patient_name: participants.patient.name, professional_name: participants.professional.name, start_time: `2030-11-0${index + 2}T10:00:00Z`, end_time: `2030-11-0${index + 2}T11:00:00Z`, type: 'video', status: 'confirmed', appointment_reason: 'Motivo sintético de cita', cancellation_reason: null }));
  const professionalAppointments = appointments.map((item, index) => ({ ...item, patient_username: participants.patient.username, type: index ? 'video' : 'in_person', status: 'confirmed' }));
  Object.assign(state, { failProfessionalDashboard: false, emptyProfessionalDashboard: false, failProfessionalCreate: false, failProfessionalCancel: false, professionalCreates: [], professionalCancels: [] });
  const notification = {
    id: '00000000-0000-4000-8000-000000000002', type: 'test', title: 'Aviso de prueba', message: 'Mensaje sintético para verificar la interfaz.',
    entity: null, entity_id: null, scheduled_for: null, read_at: null, email_required: false, email_status: 'not_required', created_at: '2026-10-25T09:00:00Z',
  };
  const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
    let raw = '';
    for await (const part of req) raw += part;
    const send = (status, data) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(data)); };
    const path = new URL(req.url, 'http://fixture.invalid').pathname;
    if (path === '/auth/forgot-password') {
      state.requestedPasswordReset = JSON.parse(raw);
      return send(202, { message_code: 'PASSWORD_RESET_REQUEST_ACCEPTED' });
    }
    if (path === '/auth/reset-password') {
      state.submittedPasswordReset = JSON.parse(raw);
      return state.limitPasswordReset ? send(429, { detail: 'PASSWORD_RESET_RATE_LIMITED' }) : send(204);
    }
    if (path === '/auth/login') {
      state.logins += 1;
      const form = new URLSearchParams(raw);
      if (!req.headers['content-type']?.startsWith('application/x-www-form-urlencoded')) return send(422, { detail: 'FORM_REQUIRED' });
      if (state.independentSessions) {
        const user = [account, participants.patient, participants.professional].find(item => item.username === form.get('username'));
        if (!user || form.get('password') !== 'TestPassword!') return send(401, { detail: 'INVALID_CREDENTIALS' });
        const id = `synthetic-session-${state.logins}`;
        const login = { user, access: `${id}-access`, refresh: `${id}-refresh`, revoked: false };
        demoSessions.push(login);
        return send(200, { access_token: login.access, refresh_token: login.refresh, token_type: 'bearer' });
      }
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
      if (state.failRefresh) return send(503, { detail: 'TEST_UNAVAILABLE' });
      if (state.independentSessions) {
        const login = demoSessions.find(item => item.refresh === JSON.parse(raw).refresh_token && !item.revoked);
        if (!login) return send(401, { detail: 'INVALID_REFRESH_TOKEN' });
        login.refresh = `${login.refresh}-rotated`;
        return send(200, { access_token: login.access, refresh_token: login.refresh, token_type: 'bearer' });
      }
      if (state.delayRefresh) await new Promise((resolve) => setTimeout(resolve, state.delayRefresh));
      state.access = 'test-rotated';
      return send(200, { access_token: state.access, refresh_token: 'test-refresh-rotated', token_type: 'bearer' });
    }
    const publicProfessional = () => ({ ...detailUser(participants.professional).professional_profile, id: participants.professional.id, name: participants.professional.name, appointment_modalities: ['in_person', 'video'] });
    if (path === '/professionals') {
      const modality = new URL(req.url, 'http://fixture.invalid').searchParams.get('appointment_type');
      const professionals = [publicProfessional()];
      if (state.testBookingDirectory && modality !== 'in_person') {
        professionals.push({ ...publicProfessional(), id: '00000000-0000-4000-8000-000000000203', name: 'Profesional solo por vídeo', appointment_modalities: ['video'] });
      }
      return send(200, { professionals, total: professionals.length, page: 1, page_size: 10 });
    }
    if (/^\/professionals\/[0-9a-f-]{36}$/.test(path)) return send(200, publicProfessional());
    const demoLogin = state.independentSessions ? demoSessions.find(item => req.headers.authorization === `Bearer ${item.access}` && !item.revoked) : null;
    if (state.independentSessions ? !demoLogin : req.headers.authorization !== `Bearer ${state.access}`) return send(401, { detail: 'INVALID_CREDENTIALS' });
    if (path === '/auth/me') return state.failMe ? send(503, { detail: 'TEST_UNAVAILABLE' }) : send(200, demoLogin?.user ?? account);
    const quickActor = demoLogin?.user ?? account;
    const availability = professionalId => ({ professional_id: professionalId, available: state.quickAvailable, reason: state.quickAvailable ? 'available' : 'outside_hours', evaluated_at: new Date().toISOString(), timezone: 'Europe/Madrid', closes_at: null });
    if (path === '/professionals/me/working-hours' && req.method === 'GET') return send(200, state.workingHours);
    if (path === '/professionals/me/working-hours/batch-delete') {
      const body = JSON.parse(raw);
      state.workingHours = state.workingHours.filter(item => !body.schedule_ids.includes(item.id)); return send(204, null);
    }
    if (path === '/professionals/me/working-hours/batch') {
      const { schedule_ids = [], days_of_week: selectedDays, ...values } = JSON.parse(raw);
      const previous = state.workingHours.filter(item => schedule_ids.includes(item.id));
      const other = state.workingHours.filter(item => !schedule_ids.includes(item.id));
      const changed = selectedDays.map(day => ({ id: previous.find(item => item.day_of_week === day)?.id ?? randomUUID(), professional_id: quickActor.id, created_at: new Date().toISOString(), ...values, day_of_week: day }));
      const next = [...other, ...changed];
      if (next.some(item => next.some(other => other.id !== item.id && other.channel === item.channel && other.day_of_week === item.day_of_week && other.is_active && item.is_active && other.start_time < item.end_time && other.end_time > item.start_time))) return send(409, { detail: 'SCHEDULE_OVERLAP' });
      state.workingHours = next; return send(200, changed);
    }
    if (path.startsWith('/professionals/me/working-hours') && req.method !== 'GET') {
      const id = path.split('/')[4];
      if (req.method === 'DELETE') { state.workingHours = state.workingHours.filter(item => item.id !== id); return send(204, null); }
      const body = JSON.parse(raw), previous = id ? state.workingHours.find(item => item.id === id) : null;
      const item = { id: randomUUID(), professional_id: quickActor.id, created_at: new Date().toISOString(), slot_duration_min: 30, is_active: true, ...previous, ...body };
      if (state.workingHours.some(other => other.id !== item.id && other.channel === item.channel && other.day_of_week === item.day_of_week && other.is_active && item.is_active && other.start_time < item.end_time && other.end_time > item.start_time)) return send(409, { detail: 'SCHEDULE_OVERLAP' });
      state.workingHours = [...state.workingHours.filter(other => other.id !== item.id), item];
      return send(id ? 200 : 201, item);
    }
    if (/^\/professionals\/[0-9a-f-]{36}\/availability$/.test(path)) {
      if (quickActor.role !== 'patient') return send(403, { detail: 'PATIENT_REQUIRED' });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      const date = params.get('requested_date'), type = params.get('appointment_type');
      const hours = type === 'in_person' ? ['09:00', '09:30'] : ['14:00', '14:30'];
      const slots = date?.endsWith('-01') ? [{ type, start_time: `${date}T${hours[0]}:00+01:00`, end_time: `${date}T${hours[1]}:00+01:00` }] : [];
      state.bookingAvailability = { date, type, slots };
      return send(200, { ...state.bookingAvailability, professional_id: path.split('/')[2] });
    }
    if (path.endsWith('/chat-availability')) return send(200, availability(path.split('/')[2]));
    const quickResponse = chat => ({ ...chat, availability: availability(chat.professional_id), can_write: chat.status === 'open' && state.quickAvailable });
    if (path === '/spontaneous-chats') {
      if (req.method === 'GET') {
        const chats = state.quickChats.filter(chat => [chat.patient_id, chat.professional_id].includes(quickActor.id));
        return send(200, { chats: chats.map(quickResponse), total: chats.length, page: 1, page_size: 20 });
      }
      if (!state.quickAvailable) return send(409, { detail: 'CHAT_OUTSIDE_AVAILABILITY' });
      const body = JSON.parse(raw);
      let chat = state.quickChats.find(item => item.patient_id === quickActor.id && item.professional_id === body.professional_id && item.status === 'open');
      if (!chat) { chat = { id: randomUUID(), patient_id: quickActor.id, professional_id: body.professional_id, patient_name: quickActor.name, professional_name: participants.professional.name, status: 'open', created_at: new Date().toISOString(), updated_at: new Date().toISOString() }; state.quickChats.push(chat); }
      return send(201, quickResponse(chat));
    }
    if (path.startsWith('/spontaneous-chats/')) {
      const id = path.split('/')[2], chat = state.quickChats.find(item => item.id === id);
      if (!chat || ![chat.patient_id, chat.professional_id].includes(quickActor.id)) return send(404, { detail: 'CHAT_NOT_FOUND' });
      if (path.endsWith('/file')) {
        const item = state.quickMessages.find(message => message.id === path.split('/')[4] && message.chat_id === id);
        if (!item?.file_name) return send(404, { detail: 'CHAT_FILE_NOT_FOUND' });
        res.writeHead(200, { 'Content-Type': item.content_type, 'Cache-Control': 'no-store' });
        res.end(item.content_type === 'image/png' ? Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64') : '%PDF-1.4 fixture'); return;
      }
      if (path.endsWith('/close')) { chat.status = 'closed'; broadcastSpontaneous(id); return send(200, quickResponse(chat)); }
      if (path.endsWith('/messages')) {
        const rows = state.quickMessages.filter(message => message.chat_id === id);
        if (req.method === 'GET') {
          const params = new URL(req.url, 'http://fixture.invalid').searchParams;
          const before = params.get('before_id'), after = params.get('after_id'), limit = Number(params.get('limit') || 50);
          const cursor = before || after, boundary = cursor ? rows.findIndex(item => item.id === cursor) : -1;
          const filtered = cursor ? rows.filter((_, index) => before ? index < boundary : index > boundary) : rows;
          return send(200, { messages: after ? filtered.slice(0, limit) : filtered.slice(-limit), has_more: filtered.length > limit });
        }
        const field = name => raw.match(new RegExp(`name="${name}"\\r\\n\\r\\n([\\s\\S]*?)\\r\\n--`))?.[1] || '';
        const clientId = field('client_id'), existing = rows.find(item => item.client_id === clientId && item.sender_id === quickActor.id);
        if (existing) return send(201, existing);
        if (!state.quickAvailable || chat.status === 'closed') return send(403, { detail: 'CHAT_OUTSIDE_AVAILABILITY' });
        const filename = raw.match(/filename="([^"]+)"/)?.[1];
        const item = { id: randomUUID(), chat_id: id, sender_id: quickActor.id, client_id: clientId, content: field('content'), file_name: filename || null, content_type: filename ? raw.match(/Content-Type: ([^\r]+)/)?.[1] || 'application/pdf' : null, file_size: filename ? 100 : null, created_at: new Date(Date.now() + rows.length).toISOString() };
        state.quickMessages.push(item); if (filename) state.quickUploads += 1;
        broadcastSpontaneous(id);
        return send(201, item);
      }
      return send(200, quickResponse(chat));
    }
    if (path === '/admin/professionals/profile-changes') return send(200, Object.values(state.profileByUser).filter(item => item.change_status === 'pending'));
    if (/^\/admin\/professionals\/[^/]+\/profile-change\/(approve|reject)$/.test(path)) {
      const body = JSON.parse(raw), id = path.split('/')[3], profile = state.profileByUser[id];
      if (!profile || profile.change_status !== 'pending' || profile.change_request_id !== body.request_id) return send(409, { detail: 'PROFILE_CHANGE_STALE' });
      if (path.endsWith('/reject') && !body.reason?.trim()) return send(422, { detail: 'PROFILE_CHANGE_REASON_REQUIRED' });
      if (path.endsWith('/approve')) { Object.assign(profile, profile.pending_changes); profile.pending_changes = null; profile.change_status = 'approved'; }
      else { profile.change_status = 'rejected'; profile.change_rejection_reason = body.reason; }
      return send(200, profile);
    }
    if (path === '/professionals/me/time-blocks') {
      if (req.method === 'POST') {
        if (state.blockConflict) return send(409, { detail: 'TIME_BLOCK_CONFLICT' });
        const block = { ...JSON.parse(raw), id: randomUUID(), professional_id: account.id, created_at: new Date().toISOString() };
        state.timeBlocks.push(block); return send(201, block);
      }
      return send(200, state.timeBlocks);
    }
    if (path.startsWith('/professionals/me/time-blocks/') && req.method === 'DELETE') {
      state.timeBlocks = state.timeBlocks.filter(item => item.id !== path.split('/').at(-1)); return send(204, null);
    }
    if (onboardingFixture(path, req.method, raw, state, send)) return;
    const followUpMatch = /^\/(professionals|patients)\/me\/appointments\/([^/]+)\/follow-up$/.exec(path);
    if (followUpMatch) {
      const actor = demoLogin?.user ?? account;
      const item = state.videoTestAppointment;
      const professional = followUpMatch[1] === 'professionals';
      if (!item || item.id !== followUpMatch[2] || item.status !== 'completed' ||
          actor.role !== (professional ? 'professional' : 'patient')) return send(404, { detail: 'NOT_FOUND' });
      if (req.method === 'PUT' && professional) {
        state.followUpNotes = JSON.parse(raw);
        state.followUpPublic = { appointment_id: item.id, start_time: item.start_time, end_time: item.end_time, type: item.type, status: 'completed',
          appointment_reason: item.appointment_reason, professional_name: actor.name,
          shared_diagnosis: state.followUpNotes.shared_diagnosis, shared_notes: state.followUpNotes.shared_notes,
          has_prescription: true };
        state.followUpNotification = { ...notification, id: randomUUID(), type: 'appointment_follow_up',
          entity: 'appointment', entity_id: item.id, read_at: null, title: 'Novedades sobre tu cita',
          message: 'Tu profesional ha compartido información sobre tu cita.' };
      }
      if (professional) return send(200, { ...item, can_edit_notes: true, ...state.followUpNotes });
      return send(200, state.followUpPublic);
    }
    if (path === '/patients/me/appointments/history') {
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      state.historyFilters = Object.fromEntries(params);
      const item = state.followUpPublic;
      const doctor = params.get('doctor')?.toLowerCase() ?? '';
      const date = item?.start_time.slice(0, 10);
      const from = params.get('from_date') || params.get('to_date');
      const to = params.get('to_date') || from;
      const rows = item && item.professional_name.toLowerCase().includes(doctor) && (!from || (from <= date && date <= to)) ? [item] : [];
      return send(200, { appointments: rows, total: rows.length, page: Number(params.get('page') || 1), page_size: 20 });
    }
    if (healthProfileFixture(path, req.method, raw, state, send)) return;
    if (path === '/patients/me/profile') {
      if (state.patientProfileFail) return send(503, { detail: 'TEST_UNAVAILABLE' });
      return send(200, { id: '00000000-0000-4000-8000-000000009001', user_id: quickActor.id, birth_date: '1995-01-01', sex_at_birth: null, height_cm: null, weight_kg: null, address: null, blood_type: null, timezone: 'Europe/Madrid', family_history_reviewed: false, onboarding_completed: false, share_health_data: false, ai_processing_consent: Boolean(state.patientConsent), ai_processing_consent_at: null, ai_consent_required: !state.patientConsent, ai_consent_code: state.patientConsent ? null : 'AI_CONSENT_REQUIRED' });
    }
    if (/^\/patients\/[^/]+\/prescriptions$/.test(path)) {
      state.patientPrescriptionPaths = [...(state.patientPrescriptionPaths || []), path];
      if (state.patientPrescriptionsFail) return send(503, { detail: 'TEST_UNAVAILABLE' });
      if (path.split('/')[2] !== (demoLogin?.user ?? account).id) return send(403, { detail: 'WRONG_USER_ID' });
      return send(200, { prescriptions: state.myPrescriptions ?? [], total: (state.myPrescriptions ?? []).length });
    }
    if (/^\/patients\/me\/appointments\/[^/]+\/prescription$/.test(path)) {
      if (state.patientPrescriptionDownloadFail) return send(404, { detail: 'Prescription file not found' });
      state.patientPrescriptionDownloads = (state.patientPrescriptionDownloads || 0) + 1;
      res.writeHead(200, { 'Content-Type': state.patientPrescriptionContentType ?? 'application/pdf', 'Content-Disposition': 'attachment; filename="recipe.pdf"' });
      res.end('%PDF-1.4 synthetic prescription'); return;
    }
    if (path === '/patients/me/ai-consent' && req.method === 'PATCH') { state.patientConsent = JSON.parse(raw).ai_processing_consent; state.patientConsentWrites = (state.patientConsentWrites || 0) + 1; return send(200, { ai_processing_consent: state.patientConsent }); }
    if (/^\/patients\/.+\/risk-(summary|history)$/.test(path)) {
      state.patientRiskPaths = [...(state.patientRiskPaths || []), path];
      if (path.split('/')[2] !== '00000000-0000-4000-8000-000000009001') return send(403, { detail: 'WRONG_PROFILE_ID' });
      if (state.patientRiskFail) return send(503, { detail: 'TEST_UNAVAILABLE' });
      if (path.endsWith('risk-history')) return send(200, { snapshots: state.patientHistory || [], next_cursor: null, trend: 'insufficient_history', ai_consent_required: !state.patientConsent });
      return send(200, { results: state.patientConsent ? (state.patientRisks || [{ model: 'bmi', status: 'insufficient_data', metric_value: null, category: null, alert_level: null, explanation: 'Test only', missing: ['height_cm', 'weight_kg'], source: 'Test source', disclaimer: 'Test disclaimer', trend: 'insufficient_history' }]) : [], sources: {}, ai_consent_required: !state.patientConsent, message_code: state.patientConsent ? null : 'AI_CONSENT_REQUIRED' });
    }
    if (path === '/patients/me/health/habits') return send(200, { habits: [], aggregates: [], total: 0, page: 1, page_size: 20 });
    if (path === '/patients/me/health/documents' && req.method === 'POST') {
      state.patientUploadCalls = (state.patientUploadCalls || 0) + 1;
      state.patientUploadMultipart = req.headers['content-type']?.startsWith('multipart/form-data') && raw.includes('name="tipo"') && raw.includes('name="file"');
      if (state.patientUploadFail) return send(422, { detail: 'Health document must be a PDF, JPEG, or PNG file' });
      return send(201, { id: randomUUID(), patient_id: '00000000-0000-4000-8000-000000009001', tipo: 'informe', descripcion: null, file_url: 'test-only', fecha_subida: new Date().toISOString() });
    }
    if (path === '/chats/appointments') {
      const actor = demoLogin?.user ?? account;
      const rows = [state.videoTestAppointment, state.inboxTestAppointment, ...professionalAppointments].filter(Boolean)
        .filter(item => [item.patient_id, item.professional_id].includes(actor.id))
        .map(item => ({ appointment_id: item.id, start_time: item.start_time, status: item.status,
          other_name: actor.role === 'patient' ? participants.professional.name : participants.patient.name, photo_url: null }));
      return send(200, { chats: rows, total: rows.length, page: 1, page_size: 20 });
    }
    if (path === '/patients/me/consentimiento' && req.method === 'PATCH') {
      state.shareHealthData = JSON.parse(raw).share_health_data;
      return send(200, { share_health_data: state.shareHealthData });
    }
    if (path === '/patients/me/appointments' && req.method === 'POST') {
      state.patientBooking = JSON.parse(raw);
      return send(201, state.patientBooking);
    }
    const patientCancellation = path.match(/^\/patients\/([^/]+)\/appointments\/([^/]+)\/cancel$/);
    if (patientCancellation && req.method === 'POST') {
      const actor = demoLogin?.user ?? account;
      const item = state.patientDashboardAppointments?.find(row => row.id === patientCancellation[2]);
      if (actor.role !== 'patient' || patientCancellation[1] !== actor.id || !item) return send(404, { detail: 'NOT_FOUND' });
      const data = JSON.parse(raw);
      state.patientCancellation = data;
      Object.assign(item, data, { status: 'cancelled' });
      return send(200, item);
    }
    if (path === '/patients/me/appointments' && req.method === 'GET') {
      if ((demoLogin?.user ?? account).role !== 'patient') return send(403, { detail: 'PATIENT_REQUIRED' });
      if (state.patientAppointmentsFail) return send(503, { detail: 'TEST_UNAVAILABLE' });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      const page = Number(params.get('page') || 1), pageSize = Number(params.get('page_size') || 20);
      const allRows = state.patientDashboardAppointments ?? (state.patientAppointmentsEmpty || !state.videoTestAppointment ? [] : [{ ...state.videoTestAppointment, professional_name: participants.professional.name }]);
      const rows = params.get('confirmed_only') === 'true' ? allRows.filter(item => item.status === 'confirmed') : allRows;
      state.patientDashboardPages = [...(state.patientDashboardPages || []), page];
      return send(200, { appointments: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, page_size: pageSize });
    }
    if (path.startsWith('/appointments/')) {
      const id = path.split('/')[2];
      const item = state.videoTestAppointment?.id === id ? state.videoTestAppointment : state.inboxTestAppointment?.id === id ? state.inboxTestAppointment : professionalAppointments.find(item => item.id === id);
      if (!item || state.chatForbidden) return send(state.chatForbidden ? 403 : 404, { detail: 'User does not participate in this appointment' });
      if (path.endsWith('/video/join')) {
        state.videoJoinCalls += 1;
        if (state.videoDenied) return send(403, { detail: 'Video join window is closed' });
        if (item.status !== 'confirmed' || item.type !== 'video') return send(403, { detail: 'Video is unavailable for this appointment' });
        return send(200, { domain: 'jitsi.fixture.invalid', room_name: `fixture-room-${id}`, jwt: 'test-video-jwt', expires_at: new Date(Date.now() + 3600000).toISOString() });
      }
      if (path.endsWith('/video/attendance')) {
        if (state.attendanceFail) return send(503, { detail: 'TEST_UNAVAILABLE' });
        const body = JSON.parse(raw);
        if (body.event === 'left') { item.status = 'completed'; state.videoStatusWrites.push({ status: 'completed' }); }
        return send(200, { status: item.status });
      }
      if (path.endsWith('/chat')) return send(200, { appointment_id: id, status: item.status, can_write: item.status === 'confirmed', participants: [{ id: (demoLogin?.user ?? account).role === 'patient' ? (demoLogin?.user ?? account).id : participants.patient.id, role: 'patient' }, { id: (demoLogin?.user ?? account).role === 'professional' ? (demoLogin?.user ?? account).id : participants.professional.id, role: 'professional' }] });
      if (path.endsWith('/chat/messages')) {
        const params = new URL(req.url, 'http://fixture.invalid').searchParams;
        const rows = state.chatMessages.filter(message => message.appointment_id === id);
        const before = rows.findIndex(message => message.id === params.get('before_id'));
        const after = rows.findIndex(message => message.id === params.get('after_id'));
        const limit = Number(params.get('limit') || 50);
        return send(200, { messages: before >= 0 ? rows.slice(Math.max(0, before - limit), before) : after >= 0 ? rows.slice(after + 1, after + 1 + limit) : rows.slice(-limit) });
      }
    }
    if (path.startsWith('/professionals/')) {
      const actor = demoLogin?.user ?? account;
      if (actor.role !== 'professional') return send(403, { detail: 'PROFESSIONAL_REQUIRED' });
      if (path === '/professionals/me/dashboard') {
        if (state.failProfessionalDashboard) return send(503, { detail: 'TEST_UNAVAILABLE' });
        const rows = state.emptyProfessionalDashboard ? [] : [...professionalAppointments, ...(state.videoTestAppointment ? [state.videoTestAppointment] : [])].filter(item => ['confirmed'].includes(item.status));
        return send(200, { timezone: 'Europe/Madrid', generated_at: '2030-10-28T12:00:00Z', date: '2030-10-28', week_start: '2030-10-28', week_end: '2030-11-03',
          appointments_today: state.emptyProfessionalDashboard ? 0 : 3, appointments_yesterday: state.emptyProfessionalDashboard ? 0 : 2, scheduled_today: state.emptyProfessionalDashboard ? 0 : 2, completed_today: state.emptyProfessionalDashboard ? 0 : 1, assigned_patients: state.emptyProfessionalDashboard ? 0 : 21,
          weekly_distribution: ['2030-10-28', '2030-10-29', '2030-10-30', '2030-10-31', '2030-11-01', '2030-11-02', '2030-11-03'].map((date, index) => ({ date, count: state.emptyProfessionalDashboard ? 0 : index === 0 ? 3 : index === 5 ? 1 : 0 })), upcoming_appointments: rows.slice(0, 5), upcoming_total: rows.length });
      }
      if (path === '/professionals/me/patients') {
        if (state.failPatients) return send(503, { detail: 'TEST_UNAVAILABLE' });
        const params = new URL(req.url, 'http://fixture.invalid').searchParams;
        const search = (params.get('search') || '').toLowerCase();
        const rows = managedUsers.filter(item => item.role === 'patient' && (!search || item.name.toLowerCase().includes(search) || item.username.toLowerCase().includes(search)));
        const page = Number(params.get('page') || 1), size = Number(params.get('page_size') || 20);
        return send(200, { patients: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size });
      }
      if (path.endsWith('/health-snapshot')) return send(200, { consent_shared: false, message_code: 'HEALTH_DATA_NOT_SHARED', allergies: [], medications: [], appointments: [], clinical_notes: [], prescriptions: [] });
      if (path.endsWith('/prescriptions')) return send(200, { prescriptions: state.patientRecipes || [], total: (state.patientRecipes || []).length, page: 1, page_size: 10 });
      if (req.method === 'GET' && path.endsWith('/prescription')) {
        if (state.failRecipeDownload) return send(404, { detail: 'Prescription file not found' });
        const recipe = (state.patientRecipes || []).find(item => item.appointment_id === path.split('/')[4]);
        if (!recipe) return send(404, { detail: 'Prescription not found' });
        state.recipeDownloads = (state.recipeDownloads || 0) + 1;
        res.writeHead(200, { 'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="fixture.pdf"' });
        res.end('%PDF-1.4 synthetic test'); return;
      }
      if (req.method === 'POST' && path.endsWith('/prescription')) {
        if (state.rejectRecipe) return send(403, { detail: 'ventana de emisión de receta expirada' });
        const field = name => new RegExp(`name="${name}"\\r\\n\\r\\n([^\\r]*)`).exec(raw)?.[1] || null;
        if (state.lateRecipe) {
          const reason = field('late_reason');
          if (!reason) return send(403, { detail: 'PRESCRIPTION_WINDOW_EXPIRED' });
          const requestId = '00000000-0000-4000-8000-000000000602';
          state.lateAlert = {
            ...notification, id: '00000000-0000-4000-8000-000000000601',
            entity_id: requestId, read_at: null,
            type: 'late_prescription_pending', title: 'Urgente · Solicitud de emisión fuera de plazo',
            scheduled_for: '2026-11-03T09:00:00Z', message: `Profesional: Dra. Ada\nMotivo de la demora: ${reason}`,
          };
          return send(202, { id: requestId, requested_at: notification.created_at });
        }
        state.recipeUploads = (state.recipeUploads || 0) + 1;
        state.recipePath = path; state.recipeBody = raw;
        if (!field('tipo') || !field('titulo') || !field('fecha_emision')) return send(422, { detail: 'METADATA_REQUIRED' });
        const item = { id: notification.id, appointment_id: path.split('/')[4], patient_id: participants.patient.id, professional_id: actor.id, file_url: 'test-only.pdf', notas: null, created_at: '2026-11-03T12:00:00Z',
          tipo: field('tipo'), titulo: field('titulo'), fecha_emision: field('fecha_emision'), fecha_caducidad: field('fecha_caducidad'),
          codigo: state.patientRecipes?.find(recipe => recipe.appointment_id === path.split('/')[4])?.codigo ?? randomUUID() };
        state.patientRecipes = [item]; return send(201, item);
      }
      if (path.endsWith('/appointments/history') && new URL(req.url, 'http://fixture.invalid').searchParams.has('patient_id')) {
        const patientId = new URL(req.url, 'http://fixture.invalid').searchParams.get('patient_id');
        return send(200, { appointments: [{ ...professionalAppointments[0], patient_id: patientId, id: '00000000-0000-4000-8000-000000000498', status: 'completed', start_time: '2026-11-03T09:00:00Z', end_time: '2026-11-03T09:30:00Z', patient_email: participants.patient.email }], total: 1, page: 1, page_size: 10 });
      }
      if (path === '/professionals/me/notification-settings') {
        if (req.method === 'PATCH') state.emailNotifications = JSON.parse(raw).email_notifications_enabled;
        return send(200, { email_notifications_enabled: state.emailNotifications ?? true });
      }
      if (path === '/professionals/me/change-password') {
        const data = JSON.parse(raw);
        if (data.current_password !== 'TestPassword123!') return send(400, { detail: 'INVALID_CURRENT_PASSWORD' });
        state.passwordChanged = true;
        return send(204);
      }
      if (path === '/professionals/me/profile') {
        const profile = state.profileByUser[actor.id] ??= detailUser(actor).professional_profile;
        if (req.method === 'PATCH') {
          const payload = JSON.parse(raw);
          state.profileUpdates.push(payload);
          profile.pending_changes = Object.fromEntries(Object.entries(payload).filter(([key, value]) => value !== profile[key]));
          profile.change_request_id = randomUUID(); profile.change_status = 'pending';
        }
        return send(200, profile);
      }
      if (path === '/professionals/me/appointments') {
        if (state.failProfessionalAppointments) return send(503, { detail: 'TEST_UNAVAILABLE' });
        const params = new URL(req.url, 'http://fixture.invalid').searchParams;
        const rows = [...professionalAppointments, ...(state.videoTestAppointment ? [state.videoTestAppointment] : [])].filter(item => (params.get('upcoming_only') === 'false' || ['confirmed'].includes(item.status)) && (!params.get('status') || item.status === params.get('status')) && (!params.get('from_date') || item.start_time.slice(0, 10) >= params.get('from_date')) && (!params.get('to_date') || item.start_time.slice(0, 10) <= params.get('to_date')));
        const page = Number(params.get('page') || 1), size = Number(params.get('page_size') || 20);
        return send(200, { appointments: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size });
      }
      if (req.method === 'PATCH' && path.endsWith('/status')) {
        const id = path.split('/')[4];
        const item = state.videoTestAppointment?.id === id ? state.videoTestAppointment : professionalAppointments.find(item => item.id === id);
        if (!item) return send(404, { detail: 'Appointment not found' });
        const body = JSON.parse(raw); state.videoStatusWrites.push(body); item.status = body.status;
        return send(200, item);
      }
      if (path.endsWith('/appointments/history')) return send(200, { appointments: [{ ...professionalAppointments[0], id: '00000000-0000-4000-8000-000000000499', status: 'cancelled', start_time: '2025-10-01T09:00:00Z', end_time: '2025-10-01T09:30:00Z', cancellation_reason: 'Cancelación sintética', room_id: 'synthetic-room', created_at: '2025-09-01T09:00:00Z', updated_at: '2025-10-01T09:00:00Z', patient_email: participants.patient.email }], total: 1, page: 1, page_size: 20 });
      if (req.method === 'POST' && path.endsWith('/cancel')) {
        if (state.failProfessionalCancel) return send(409, { detail: 'TEST_CONFLICT' });
        const item = professionalAppointments.find(item => item.id === path.split('/')[4]);
        if (!item) return send(404, { detail: 'Appointment not found' });
        const body = JSON.parse(raw); state.professionalCancels.push(body);
        item.status = 'cancelled'; item.cancellation_reason = body.cancellation_reason; return send(200, item);
      }
      if (req.method === 'POST' && path.endsWith('/appointments')) {
        if (state.failProfessionalCreate) return send(409, { detail: 'TEST_CONFLICT' });
        const body = JSON.parse(raw); state.professionalCreates.push(body);
        const item = { ...body, id: `00000000-0000-4000-8000-${String(901 + state.professionalCreates.length).padStart(12, '0')}`, professional_id: actor.id, patient_name: participants.patient.name, patient_username: participants.patient.username, status: 'confirmed', cancellation_reason: null };
        professionalAppointments.unshift(item); return send(201, item);
      }
    }
    if (!state.userManagement && path.startsWith('/admin/users/') && req.method === 'GET') {
      if (account.role !== 'admin') return send(403, { detail: 'ADMIN_REQUIRED' });
      if (state.failAuditNames) return send(503, { detail: 'TEST_UNAVAILABLE' });
      const id = path.split('/').at(-1);
      const item = [account, participants.patient, participants.professional].find(item => item.id === id);
      return item ? send(200, detailUser(item)) : send(404, { detail: 'User not found' });
    }
    if (state.userManagement && (path.startsWith('/admin/users') || path.startsWith('/admin/professionals/'))) {
      if (account.role !== 'admin') return send(403, { detail: 'ADMIN_REQUIRED' });
      if (req.method !== 'GET' && state.userFailure) return send(state.userFailure.status, { detail: state.userFailure.detail });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      if (path === '/admin/users' && req.method === 'GET') {
        if (state.failUsers) return send(503, { detail: 'TEST_UNAVAILABLE' });
        state.userQueries.push(Object.fromEntries(params));
        const search = (params.get('search') || '').toLowerCase();
        const rows = managedUsers.filter(item => (!params.get('role') || item.role === params.get('role')) && (!search || [item.name, item.email, item.username].some(value => value.toLowerCase().includes(search))));
        const page = Number(params.get('page') || 1), size = Number(params.get('page_size') || 20);
        return send(200, { users: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size });
      }
      if (path === '/admin/users' && req.method === 'POST') {
        const { password, ...body } = JSON.parse(raw);
        void password;
        state.userWrites.push({ method: 'POST', ...JSON.parse(raw) });
        const item = { ...account, ...body, id: `00000000-0000-4000-8000-${String(801 + state.userWrites.length).padStart(12, '0')}`, is_active: body.role !== 'professional' };
        if (item.professional_profile) Object.assign(item.professional_profile, { id: item.id, user_id: item.id, approval_status: 'pending', rejection_reason: null, reviewed_at: null, reviewed_by: null });
        managedUsers.unshift(item); return send(201, detailUser(item));
      }
      const id = path.split('/')[3];
      const item = managedUsers.find(item => item.id === id);
      if (!item) return send(404, { detail: 'User not found' });
      if (req.method === 'GET') return send(200, detailUser(item));
      if (path.endsWith('/approve')) {
        item.professional_profile.approval_status = 'approved'; item.is_active = true;
        return send(200, item.professional_profile);
      }
      if (req.method === 'PATCH') {
        const { password, ...body } = JSON.parse(raw); void password;
        state.userWrites.push({ method: 'PATCH', ...JSON.parse(raw) }); Object.assign(item, body); return send(200, detailUser(item));
      }
      if (req.method === 'DELETE') {
        managedUsers.splice(managedUsers.indexOf(item), 1); res.writeHead(204); res.end(); return;
      }
    }
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
      const rows = appointments.filter(item => item.status === 'confirmed');
      return send(200, { appointments: rows.slice(0, 3), total: rows.length, period_start: '2030-11-01T00:00:00Z', period_end: '2030-12-01T00:00:00Z', timezone: 'Europe/Madrid' });
    }
    if (path === '/admin/appointments') {
      if (account.role !== 'admin') return send(403, { detail: 'ADMIN_REQUIRED' });
      if (req.method === 'POST') {
        if (state.failCreateAppointment) return send(409, { detail: 'TEST_CONFLICT' });
        const body = JSON.parse(raw); state.appointmentCreates.push(body);
        const item = { ...body, id: `00000000-0000-4000-8000-${String(400 + state.appointmentCreates.length).padStart(12, '0')}`, patient_name: participants.patient.name, professional_name: participants.professional.name, status: 'confirmed', appointment_reason: body.appointment_reason ?? null, cancellation_reason: null };
        appointments.push(item); return send(201, item);
      }
      if (state.failAppointments) return send(503, { detail: 'TEST_UNAVAILABLE' });
      const params = new URL(req.url, 'http://fixture.invalid').searchParams;
      state.appointmentQueries.push(Object.fromEntries(params));
      let rows = appointments.filter(item => (!params.get('patient_id') || item.patient_id === params.get('patient_id')) && (!params.get('professional_id') || item.professional_id === params.get('professional_id')) && (!params.get('from_date') || item.start_time.slice(0, 10) >= params.get('from_date')) && (!params.get('to_date') || item.start_time.slice(0, 10) <= params.get('to_date')) && (params.get('upcoming_month') !== 'true' || ['confirmed'].includes(item.status)));
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
      let rows = Array.from({ length: 21 }, (_, index) => ({ id: `00000000-0000-4000-8000-${String(index + 100).padStart(12, '0')}`, actor_id: account.id, actor_role: 'admin', patient_id: index === 20 ? participants.patient.id : null, accion: index % 2 ? 'lectura' : 'modificacion', entidad: index === 20 ? 'appointment' : 'user_role', entidad_id: index === 20 ? appointments[0].id : participants.professional.id, fecha_hora: '2026-10-30T12:00:00Z' }));
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
      if (demoLogin) demoLogin.revoked = true;
      else state.access = 'revoked-test-token';
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
    if (path === '/notifications') return send(200, {
      notifications: state.empty ? [] : [
        ...((demoLogin?.user ?? account).role === 'admin' && state.lateAlert ? [state.lateAlert] : []),
        ...((demoLogin?.user ?? account).role === 'patient' && state.followUpNotification ? [state.followUpNotification] : []),
        notification,
      ],
      next_cursor: null,
    });
    if (req.method === 'POST' && (demoLogin?.user ?? account).role === 'admin' && state.lateAlert &&
        path === `/admin/late-prescription-requests/${state.lateAlert.entity_id}/approve`) {
      state.lateAlert.type = 'late_prescription_reviewed';
      state.lateAlert.title = 'Solicitud de emisión fuera de plazo autorizada';
      res.writeHead(204); res.end(); return;
    }
    if (path === `/notifications/${notification.id}/read` && req.method === 'PATCH') {
      state.reads += 1; notification.read_at = '2026-10-25T10:00:00Z'; return send(200, notification);
    }
    send(404, { detail: 'TEST_NOT_FOUND' });
  });
  server.on('upgrade', (req, socket) => {
    const url = new URL(req.url, 'http://fixture.invalid');
    const token = url.searchParams.get('token');
    const login = state.independentSessions ? demoSessions.find(item => item.access === token && !item.revoked) : null;
    if ((state.independentSessions ? !login : token !== state.access) || !(/^\/ws\/(chat|spontaneous-chat)\//.test(url.pathname))) { socket.destroy(); return; }
    const actor = login?.user ?? account;
    const appointmentId = (url.pathname.includes('/spontaneous-chat/') ? 'spontaneous:' : '') + url.pathname.split('/').at(-1);
    const accept = createHash('sha1').update(req.headers['sec-websocket-key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
    chatConnections.set(socket, appointmentId);
    function write(target, message) {
      const data = Buffer.from(JSON.stringify(message));
      const header = Buffer.alloc(data.length < 126 ? 2 : 4); header[0] = 0x81;
      if (data.length < 126) header[1] = data.length;
      else { header[1] = 126; header.writeUInt16BE(data.length, 2); }
      target.write(Buffer.concat([header, data]));
    }
    broadcastSpontaneous = id => { for (const [target, room] of chatConnections) if (room === `spontaneous:${id}`) write(target, { type: 'changed' }); };
    let buffer = Buffer.alloc(0);
    socket.on('data', chunk => {
      buffer = Buffer.concat([buffer, chunk]);
      while (buffer.length >= 2) {
        const opcode = buffer[0] & 15, masked = Boolean(buffer[1] & 128);
        let length = buffer[1] & 127, offset = 2;
        if (length === 126) { if (buffer.length < 4) return; length = buffer.readUInt16BE(2); offset = 4; }
        if (length === 127) { socket.destroy(); return; }
        if (buffer.length < offset + (masked ? 4 : 0) + length) return;
        const mask = masked ? buffer.subarray(offset, offset + 4) : null; if (masked) offset += 4;
        const data = Buffer.from(buffer.subarray(offset, offset + length));
        if (mask) for (let i = 0; i < data.length; i += 1) data[i] ^= mask[i % 4];
        buffer = buffer.subarray(offset + length);
        if (opcode === 8) { socket.end(Buffer.from([0x88, 0])); return; }
        if (opcode !== 1) continue;
        let message; try { message = JSON.parse(data.toString()); } catch { continue; }
        if (message.type === 'ping') { write(socket, { type: 'pong' }); continue; }
        if (message.type === 'typing') {
          for (const [target, room] of chatConnections) if (room === appointmentId) write(target, { type: 'typing', sender_id: actor.id, is_typing: message.is_typing });
          continue;
        }
        if (message.type === 'message') {
          const item = { id: randomUUID(), appointment_id: appointmentId, sender_id: actor.id, content: message.content, created_at: new Date().toISOString() };
          state.chatMessages.push(item);
          for (const [target, room] of chatConnections) if (room === appointmentId) write(target, { type: 'message', ...item });
        }
      }
    });
    socket.on('close', () => chatConnections.delete(socket));
    socket.on('error', () => chatConnections.delete(socket));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Test server address missing');
  return { state, account, participants, notification, chatConnections, url: `http://127.0.0.1:${address.port}`, close: () => { for (const socket of chatConnections.keys()) socket.destroy(); return new Promise((resolve) => server.close(resolve)); } };
}
