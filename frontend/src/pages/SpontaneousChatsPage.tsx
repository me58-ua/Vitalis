import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { getChatDoctors, listSpontaneousChats, startSpontaneousChat, spontaneousChatError, availabilityLabels } from '../api/spontaneousChat';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { SpontaneousChatRoom } from '../components/SpontaneousChatRoom';
import type { SpontaneousChatPage } from '../types/api';
import '../styles/spontaneous-chat.css';

function DoctorPicker({ onStarted }: { onStarted: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState({ search: '', page: 1 });
  const load = useCallback((signal: AbortSignal) => getChatDoctors(query.search, query.page, signal), [query]);
  const state = useAdminQuery(load, spontaneousChatError);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null), locked = useRef(false);
  useEffect(() => () => controller.current?.abort(), []);
  async function start(id: string) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(''); const abort = new AbortController(); controller.current = abort;
    try { const chat = await startSpontaneousChat(id, abort.signal); if (!abort.signal.aborted) onStarted(chat.id); }
    catch (error: unknown) { if (!abort.signal.aborted) { setError(spontaneousChatError(error)); state.retry(); } }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  return <section className="spontaneous-doctors"><h2>Consulta rápida sin cita</h2><p>Elige un médico disponible para una consulta breve. Esta conversación no te incorpora a su lista de pacientes.</p>
    <form className="spontaneous-search" onSubmit={event => { event.preventDefault(); setQuery({ search: search.trim(), page: 1 }); }}><label>Buscar médico por nombre<input name="chat_doctor_search" maxLength={100} value={search} onChange={event => setSearch(event.target.value)} disabled={busy} /></label><button className="button secondary" disabled={busy}>Buscar médico</button><button className="text-button" type="button" disabled={busy || state.loading} onClick={state.retry}>Actualizar disponibilidad</button></form>
    {state.loading && <p role="status">Consultando disponibilidad…</p>}{(state.error || error) && <div className="error-state" role="alert"><p>{error || state.error}</p><button disabled={busy} onClick={state.retry}>Reintentar médicos</button></div>}
    {state.data?.professionals.length === 0 && <p>No se han encontrado médicos.</p>}
    <ul>{state.data?.professionals.map(doctor => <li key={doctor.id}><strong>{doctor.name}</strong><p>{doctor.specialty}</p><p>{availabilityLabels[doctor.availability.reason]}</p><button className="button primary" disabled={busy || !doctor.availability.available} onClick={() => { void start(doctor.id); }}>Iniciar chat</button></li>)}</ul>
    {state.data && <nav aria-label="Páginas de médicos"><button className="text-button" disabled={busy || query.page <= 1} onClick={() => setQuery({ ...query, page: query.page - 1 })}>Anterior</button><span>Página {query.page}</span><button className="text-button" disabled={busy || query.page * state.data.page_size >= state.data.total} onClick={() => setQuery({ ...query, page: query.page + 1 })}>Siguiente</button></nav>}
  </section>;
}

export function SpontaneousChatsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get('chat');
  const [page, setPage] = useState(1), [revision, setRevision] = useState(0);
  const [result, setResult] = useState<SpontaneousChatPage | null>(null), [error, setError] = useState('');
  const [newChat, setNewChat] = useState(false);
  useEffect(() => {
    const abort = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { const data = await listSpontaneousChats(page, abort.signal); if (!abort.signal.aborted) { setResult(data); setError(''); } }
      catch (error: unknown) { if (!abort.signal.aborted) setError(spontaneousChatError(error)); }
      finally { if (!abort.signal.aborted) timer = setTimeout(() => { void poll(); }, 5000); }
    }
    void poll(); return () => { abort.abort(); clearTimeout(timer); };
  }, [page, revision]);
  if (!user) return null;
  const refresh = () => setRevision(value => value + 1);
  return <main id="contenido" className="spontaneous-main"><header className="spontaneous-heading"><h1>Mensajes</h1><p>Conversaciones breves con horario propio, independientes de las citas y de «Mis pacientes».</p>{user.role === 'patient' && <button className="button primary" aria-expanded={newChat} onClick={() => setNewChat(value => !value)}>Nueva consulta por chat</button>}</header>
    {newChat && user.role === 'patient' && <DoctorPicker onStarted={id => { setParams({ chat: id }); setNewChat(false); refresh(); }} />}
    <div className="spontaneous-layout"><aside className="spontaneous-inbox" aria-label="Tus conversaciones"><h2>Conversaciones</h2><button className="text-button" onClick={refresh}>Actualizar chats</button>{!result && !error && <p role="status">Cargando chats…</p>}{error && <div className="error-state" role="alert"><p>{error}</p><button onClick={refresh}>Reintentar chats</button></div>}{result?.chats.length === 0 && <p>No tienes conversaciones todavía.</p>}
      <ul>{result?.chats.map(chat => <li key={chat.id}><button className="spontaneous-thread" aria-pressed={selectedId === chat.id} onClick={() => setParams({ chat: chat.id })}><strong>{user.role === 'patient' ? chat.professional_name : chat.patient_name}</strong><span>{chat.status === 'closed' ? 'Cerrada' : availabilityLabels[chat.availability.reason]}</span></button></li>)}</ul>
      {result && <nav aria-label="Páginas de chats"><button className="text-button" disabled={page <= 1} onClick={() => { setResult(null); setPage(value => value - 1); }}>Anterior</button><span>Página {page}</span><button className="text-button" disabled={page * result.page_size >= result.total} onClick={() => { setResult(null); setPage(value => value + 1); }}>Siguiente</button></nav>}
    </aside>{selectedId ? <SpontaneousChatRoom key={selectedId} id={selectedId} user={user} onChanged={refresh} /> : <section className="spontaneous-empty"><h2>Selecciona una conversación</h2><p>{user.role === 'patient' ? 'También puedes iniciar una consulta con un médico disponible.' : 'Las consultas de pacientes aparecerán aquí. Configura tus horas de chat desde Agenda.'}</p></section>}</div>
  </main>;
}
