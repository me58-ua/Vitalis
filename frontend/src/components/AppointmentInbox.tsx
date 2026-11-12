import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { consultationError } from '../api/consultations';
import { useAuth } from '../auth/AuthContext';
import { ConsultationChat } from './ConsultationChat';
import { UserAvatar } from './UserAvatar';
import { appointmentDate } from './AppointmentSummary';
import type { components } from '../types/api.generated';
import '../styles/appointment-inbox.css';

type Inbox = components['schemas']['ChatInboxResponse'];

export function AppointmentInbox() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const selected = params.get('appointment');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Inbox | null>(null);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    void api.get<Inbox>('/chats/appointments', { params: { page, page_size: 20 }, signal: abort.signal })
      .then(response => { if (!abort.signal.aborted) { setData(response.data); setError(''); } })
      .catch((reason: unknown) => { if (!abort.signal.aborted) setError(consultationError(reason)); });
    return () => abort.abort();
  }, [page, revision]);
  if (!user) return null;
  const current = data?.chats.find(chat => chat.appointment_id === selected);
  return <div className={`appointment-inbox${selected ? ' has-selection' : ''}`}>
    <aside aria-label="Chats de tus citas" className="appointment-threads">
      <header><h2>Videoconsultas</h2><button className="text-button" onClick={() => setRevision(value => value + 1)}>Actualizar</button></header>
      <label className="appointment-search">Buscar conversaciones<input type="search" value={search} placeholder="Nombre del paciente o médico…" onChange={event => setSearch(event.target.value)} /></label>
      {error && <p role="alert">{error}</p>}{!data && !error && <p role="status">Cargando conversaciones…</p>}
      {data?.total === 0 && <p>No tienes chats de citas todavía.</p>}
      <ul>{data?.chats.filter(chat => chat.other_name.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(chat => <li key={chat.appointment_id}>
        <button className="appointment-thread" aria-pressed={selected === chat.appointment_id} onClick={() => setParams({ appointment: chat.appointment_id })}>
          <UserAvatar key={chat.photo_url} name={chat.other_name} photoUrl={chat.photo_url} />
          <span><strong>{chat.other_name} · Videoconsulta</strong><time dateTime={chat.start_time}>{appointmentDate(chat.start_time)}</time><small>{chat.status === 'completed' ? 'Finalizada · Solo lectura' : 'Solo se puede escribir durante la cita'}</small></span>
        </button></li>)}</ul>
      {data && data.total > data.page_size && <nav aria-label="Páginas de conversaciones"><button disabled={page <= 1} onClick={() => { setPage(value => value - 1); }}>Anterior</button><span>{page}</span><button disabled={page * data.page_size >= data.total} onClick={() => setPage(value => value + 1)}>Siguiente</button></nav>}
    </aside>
    <div className="appointment-conversation">{selected ? <><button className="text-button appointment-back" onClick={() => setParams({ section: 'video' })}>Volver a conversaciones</button><ConsultationChat key={selected} appointmentId={selected} userId={user.id} otherName={current ? `${current.other_name} · Videoconsulta` : 'Chat de la videoconsulta'} photoUrl={current?.photo_url} /></>
      : <div className="appointment-empty"><h2>Tu consulta, también por mensaje</h2><p>Selecciona una cita para conversar con tu {user.role === 'patient' ? 'médico' : 'paciente'}.</p></div>}</div>
  </div>;
}
