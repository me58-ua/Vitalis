import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { PatientDashboardLayout } from '../../layouts/PatientDashboardLayout';
import { answerOnboarding, confirmOnboarding, getOnboarding, giveOnboardingConsent, onboardingError, type OnboardingReview, type OnboardingState } from '../../api/onboarding';
import logo from '../../assets/figma/patient/VitaLisLogo.png';
import '../../styles/patient-onboarding.css';

const modules = [
  { title: 'Alergias', description: 'Sustancias y gravedad', ids: ['allergies'] },
  { title: 'Condiciones crónicas', description: 'Diagnósticos previos', ids: ['chronic_conditions'] },
  { title: 'Medicación actual', description: 'Medicamentos, dosis y frecuencia', ids: ['medication'] },
  { title: 'Datos físicos', description: 'Altura y peso', ids: ['height', 'weight'] },
  { title: 'Hábitos de vida', description: 'Alcohol, tabaco, ejercicio, sueño y dieta', ids: ['auditc_frequency', 'auditc_quantity', 'auditc_binge', 'tobacco', 'exercise', 'sleep', 'diet'] },
  { title: 'Antecedentes familiares', description: 'Parentesco y enfermedades', ids: ['family_history'] },
];

function Assistant({ children }: { children: React.ReactNode }) {
  return <div className="onboarding-message assistant"><img className="onboarding-avatar" src={logo} alt="" /><div><span className="onboarding-speaker">Asistente de salud vitaLis</span><div className="onboarding-bubble">{children}</div></div></div>;
}
function AnswerReview({ review }: { review: OnboardingReview }) {
  return <><Assistant><p>{review.question}</p></Assistant><div className="onboarding-message patient"><div><span className="onboarding-speaker">Tú</span><div className="onboarding-bubble"><p>{review.answer}</p></div></div></div><Assistant><strong>Datos confirmados ✓</strong><ul>{review.summary.map((line, i) => <li key={i}>{line}</li>)}</ul></Assistant></>;
}

export function PatientOnboardingPage() {
  const { user } = useAuth();
  return user ? <OnboardingChat key={user.id} /> : null;
}

function OnboardingChat() {
  const navigate = useNavigate();
  const [state, setState] = useState<OnboardingState | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const flight = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement | null>(null);
  const input = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    getOnboarding(abort.signal).then(data => { if (!abort.signal.aborted) setState(data); }).catch(failure => { if (!abort.signal.aborted) setError(onboardingError(failure)); });
    return () => { abort.abort(); flight.current?.abort(); };
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, [state, busy]);
  useEffect(() => { if (state?.stage === 'question' && !busy) input.current?.focus({ preventScroll: true }); }, [state?.stage, state?.question?.id, busy]);

  async function act(operation: (signal: AbortSignal) => Promise<OnboardingState>, clear = false) {
    if (flight.current) return;
    const abort = new AbortController(); flight.current = abort; setBusy(true); setError('');
    try {
      const next = await operation(abort.signal);
      if (!abort.signal.aborted) { setState(next); if (clear) setMessage(''); }
    } catch (failure: unknown) { if (!abort.signal.aborted) setError(onboardingError(failure)); }
    finally { if (!abort.signal.aborted) { flight.current = null; setBusy(false); } }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (state?.stage === 'question' && state.question && message.trim()) void act(signal => answerOnboarding(state.question!.id, message.trim(), signal), true);
  }
  const completed = state?.stage === 'completed';
  const consented = state && !['consent', 'declined'].includes(state.stage);
  const confirmedIds = new Set(state?.confirmed_answers?.map(item => item.question_id));
  const progress = state ? Math.round(state.completed_questions / state.total_questions * 100) : 0;
  return <PatientDashboardLayout onProfile={() => navigate('/patientPanel')}><main id="contenido" className="onboarding-main">
    <header className="onboarding-heading"><div><span className="onboarding-eyebrow">TU PERFIL DE SALUD, PASO A PASO</span><h1>Completa tu perfil de salud</h1><p>Cuéntanos sobre tu salud y confirma cada respuesta antes de guardarla.</p></div><Link className="button secondary" to="/patientPanel">Guardar y pausar</Link></header>
    <ol className="onboarding-steps" aria-label="Progreso del registro"><li aria-current={!consented ? 'step' : undefined} className={consented ? 'done' : 'current'}><span>{consented ? '✓' : '1'}</span><div><small>Paso 1</small><strong>Tu consentimiento</strong></div></li><li aria-current={consented && !completed ? 'step' : undefined} className={completed ? 'done' : consented ? 'current' : ''}><span>{completed ? '✓' : '2'}</span><div><small>Paso 2</small><strong>Responde y confirma</strong></div></li><li aria-current={completed ? 'step' : undefined} className={completed ? 'done' : ''}><span>{completed ? '✓' : '3'}</span><div><small>Paso 3</small><strong>Perfil completado</strong></div></li></ol>
    <div className="onboarding-columns"><section className="onboarding-chat" aria-label="Conversación de registro de salud"><p className="onboarding-notice">Este asistente ayuda a completar tu perfil y no sustituye la valoración de un profesional sanitario.</p>
      <div className="onboarding-stream" role="log" aria-label="Preguntas, respuestas y confirmaciones" aria-live="polite" aria-relevant="additions text">
        {!state && !error && <p role="status">Cargando tu conversación…</p>}
        {state?.stage === 'consent' && <Assistant><h2>Antes de empezar</h2><p>Para organizar tus respuestas y evaluar riesgos de salud, necesitamos tu consentimiento para procesar tus datos de salud mediante inteligencia artificial de Gemini (Google).</p><p>Es voluntario. Puedes retirar el consentimiento desde tu perfil. Compartir datos con profesionales es un permiso separado.</p><p><strong>¿Aceptas este procesamiento de tus datos?</strong></p><div className="onboarding-actions"><button className="button primary" disabled={busy} onClick={() => { void act(signal => giveOnboardingConsent(true, signal)); }}>Sí, acepto</button><button className="button secondary" disabled={busy} onClick={() => { void act(signal => giveOnboardingConsent(false, signal)); }}>No, no acepto</button></div></Assistant>}
        {state?.stage === 'declined' && <Assistant><h2>Tu decisión está guardada</h2><p>{state.message}</p><div className="onboarding-actions"><Link className="button primary" to="/patientPanel">Volver a mi panel</Link><button className="button secondary" disabled={busy} onClick={() => { void act(signal => giveOnboardingConsent(true, signal)); }}>Dar mi consentimiento</button></div></Assistant>}
        {consented && <><Assistant><p>¡Hola! Vamos a completar tu perfil pregunta a pregunta.</p><p><strong>Intenta responder a cada pregunta en un solo mensaje, no en varios.</strong> Después te mostraré un resumen para que lo confirmes con OK o lo corrijas. Solo entonces pasaremos a la siguiente pregunta.</p><p>Si no conoces un dato, puedes responder «no sé».</p></Assistant>
          {state.confirmed_answers?.map(review => <AnswerReview key={review.question_id} review={review} />)}
          {state.question && <Assistant><p>{state.question.text}</p>{state.stage === 'question' && (state.question.options?.length ?? 0) > 0 && <div className="onboarding-options">{state.question.options?.map(option => <button key={option} disabled={busy} onClick={() => setMessage(option)} aria-pressed={message === option}>{option}</button>)}</div>}</Assistant>}
          {state.pending && <><div className="onboarding-message patient"><div><span className="onboarding-speaker">Tú</span><div className="onboarding-bubble"><p>{state.pending.answer}</p></div></div></div><Assistant><div className="onboarding-confirmation"><span className="onboarding-eyebrow">REVISA TU RESPUESTA</span><h2>¿Son correctos estos datos?</h2><ul>{state.pending.summary.map((line, index) => <li key={index}>{line}</li>)}</ul><p>Estos datos aún no se han añadido a tu historial de salud.</p><div className="onboarding-actions"><button className="button primary" disabled={busy} onClick={() => { void act(signal => confirmOnboarding(state.pending!.draft_id, true, signal)); }}>OK, confirmar</button><button className="button secondary" disabled={busy} onClick={() => { const answer = state.pending!.answer; void act(signal => confirmOnboarding(state.pending!.draft_id, false, signal)).then(() => setMessage(answer)); }}>Corregir respuesta</button></div></div></Assistant></>}
          {completed && <Assistant><h2>¡Tu perfil de salud está completado!</h2><p>Has revisado y confirmado todas las respuestas. Los datos que no conocías quedan pendientes. Puedes consultar tus evaluaciones en tu panel.</p><Link className="button primary" to="/patientPanel">Ir a mi panel</Link></Assistant>}
        </>}
        {busy && <p className="onboarding-working" role="status">{state?.stage === 'question' ? 'Interpretando tu respuesta…' : 'Guardando tu decisión…'}</p>}
        <div ref={end} />
      </div>
      {error && <div className="onboarding-error" role="alert"><p>{error}</p><button className="text-button" disabled={busy} onClick={() => { void act(getOnboarding); }}>Actualizar conversación</button></div>}
      {state?.stage === 'question' && <form className="onboarding-composer" onSubmit={submit}><label htmlFor="onboarding-answer">Tu respuesta en un solo mensaje</label><div><textarea id="onboarding-answer" name="onboarding-answer" ref={input} rows={2} maxLength={4000} value={message} disabled={busy} onChange={event => setMessage(event.target.value)} placeholder="Escribe tu respuesta aquí…" required /><button className="button primary" type="submit" disabled={busy || !message.trim()}>Enviar <span aria-hidden="true">➤</span></button></div><small>{message.length}/4000 · Revisarás el resumen antes de confirmar.</small></form>}
      <footer className="onboarding-chat-footer">Puedes pausar y volver a esta conversación. Las respuestas confirmadas y el resumen pendiente se conservan.</footer>
    </section><aside className="onboarding-side"><section className="onboarding-modules"><h2>Módulos del perfil</h2><p>Cada sección avanza cuando confirmas tus datos.</p><label htmlFor="onboarding-progress">{state?.completed_questions ?? 0} de {state?.total_questions ?? 13} preguntas confirmadas</label><progress id="onboarding-progress" value={progress} max={100}>{progress}%</progress><ul>{modules.map(module => {
      const active = Boolean(consented && state?.question && module.ids.includes(state.question.id));
      const done = Boolean(consented && module.ids.every(id => confirmedIds.has(id) || (['auditc_quantity', 'auditc_binge'].includes(id) && state.total_questions === 11)));
      return <li key={module.title} className={active ? 'active' : done ? 'done' : ''}><span className="onboarding-module-icon" aria-hidden="true">{done ? '✓' : active ? '●' : '○'}</span><div><h3>{module.title}</h3><p>{module.description}</p><small>{done ? 'Confirmado' : active ? state?.stage === 'confirmation' ? 'Pendiente de tu OK' : 'En conversación' : 'Pendiente'}</small></div></li>;
    })}</ul><p className="onboarding-save-note">Solo se guardan datos en tu historial después de tu OK.</p></section><section className="onboarding-privacy"><h2>Tú decides</h2><p>Revisa cada resumen y corrige cualquier dato antes de confirmarlo. Puedes continuar en otro momento.</p></section></aside></div>
  </main></PatientDashboardLayout>;
}
