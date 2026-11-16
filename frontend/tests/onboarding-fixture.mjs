// Synthetic browser contract fixture; backend extraction/persistence has its own tests.
const questions = [
  ['allergies', '¿Tienes alguna alergia?', 'alergias'],
  ['chronic_conditions', '¿Tienes alguna enfermedad crónica diagnosticada?', 'enfermedades_cronicas'],
  ['medication', '¿Tomas actualmente algún medicamento?', 'medicacion'],
  ['height', '¿Cuál es tu altura en centímetros?', 'cuerpo'],
  ['weight', '¿Cuál es tu peso en kilogramos?', 'cuerpo'],
  ['auditc_frequency', '¿Con qué frecuencia consume alguna bebida alcohólica?', 'alcohol'],
  ['auditc_quantity', '¿Cuántas consumiciones bebe en un día de consumo normal?', 'alcohol'],
  ['auditc_binge', '¿Con qué frecuencia toma 6 o más bebidas?', 'alcohol'],
  ['tobacco', '¿Cuántos cigarrillos fumas al día?', 'habitos'],
  ['exercise', '¿Cuántos minutos dedicas al ejercicio a la semana?', 'habitos'],
  ['sleep', '¿Cuántas horas duermes normalmente cada noche?', 'habitos'],
  ['diet', '¿Cuántas raciones de fruta y verdura consumes al día?', 'habitos'],
  ['family_history', '¿Tienes antecedentes familiares de alguna enfermedad importante?', 'antecedentes_familiares'],
];
export function onboardingFixture(path, method, raw, state, send) {
  if (!path.startsWith('/onboarding/chat')) return false;
  const chat = state.onboarding ??= { stage: 'consent', question: null, pending: null, confirmed_answers: [], skipped_questions: [], auto_skipped_questions: [], is_update: false, completed_questions: 0, total_questions: questions.length };
  const nextQuestion = () => {
    const [id, text, block] = questions[chat.completed_questions];
    return { id, text, block, options: id === 'auditc_frequency' ? ['Nunca', 'Mensualmente o menos', 'De 2 a 4 veces al mes', 'De 2 a 3 veces a la semana', '4 o más veces a la semana'] : [] };
  };
  const data = raw ? JSON.parse(raw) : {};
  if (method === 'GET') { send(200, chat); return true; }
  if (path.endsWith('/restart')) {
    if (!['question', 'confirmation'].includes(chat.stage)) Object.assign(chat, { stage: 'question', current: 0, question: null, pending: null, confirmed_answers: [], skipped_questions: [], completed_questions: 0, is_update: true });
    chat.question = nextQuestion();
  } else if (path.endsWith('/skip')) {
    if (!chat.skipped_questions.includes(data.question_id)) {
      if (chat.stage !== 'question' || chat.question.id !== data.question_id) { send(409, { detail: 'Pregunta incorrecta' }); return true; }
      chat.skipped_questions.push(data.question_id); chat.completed_questions += 1;
    }
    chat.stage = chat.completed_questions === questions.length ? 'completed' : 'question';
    chat.question = chat.stage === 'question' ? nextQuestion() : null;
  } else if (path.endsWith('/consent')) {
    chat.stage = data.accepted ? 'question' : 'declined';
    chat.question = data.accepted ? nextQuestion() : null;
    chat.message = data.accepted ? null : 'Sin tu consentimiento no podemos utilizar tu información para evaluar riesgos de salud. Por eso no te haremos las preguntas.';
  } else if (path.endsWith('/answer')) {
    state.onboardingAnswers = (state.onboardingAnswers ?? 0) + 1;
    if (state.onboardingFail) { send(503, { detail: 'No se pudo interpretar tu respuesta con la IA. Inténtalo de nuevo; seguimos en la misma pregunta.' }); return true; }
    if (chat.stage !== 'question' || data.question_id !== chat.question.id) { send(409, { detail: 'Pregunta incorrecta' }); return true; }
    chat.pending = { draft_id: `draft-${state.onboardingAnswers}`, question_id: chat.question.id, question: chat.question.text, answer: data.message, summary: [`Resumen sintético: ${data.message}`] };
    chat.stage = 'confirmation';
  } else if (path.endsWith('/confirm')) {
    if (data.draft_id !== chat.pending?.draft_id) { send(409, { detail: 'Confirmación incorrecta' }); return true; }
    if (data.confirmed) {
      if (chat.is_update && chat.pending.question_id === 'weight') state.healthProfile.profile.weight_kg = Number.parseFloat(chat.pending.answer);
      chat.confirmed_answers.push(chat.pending); chat.completed_questions += 1;
      state.onboardingSaves = (state.onboardingSaves ?? 0) + 1;
    }
    chat.pending = null;
    chat.stage = chat.completed_questions === questions.length ? 'completed' : 'question';
    chat.question = chat.stage === 'question' ? nextQuestion() : null;
  }
  send(200, chat);
  return true;
}
