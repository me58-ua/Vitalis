import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Modal } from './Modal';
import { searchDocuments, downloadDocument, type DocumentSearch as SearchPage, type DocumentItem, type DocumentType } from '../api/documents';
import { errorMessage } from '../api/errors';
import type { User } from '../types/api';
import searchIcon from '../assets/figma/imgMargin.svg';

export function DocumentSearch({ user }: { user: User }) {
  const [open, setOpen] = useState(false);
  return <>
    <button className="search-trigger" onClick={() => setOpen(true)}><img src={searchIcon} alt="" /><span>Buscar documentos médicos</span></button>
    {open && <SearchDialog user={user} onClose={() => setOpen(false)} />}
  </>;
}

const types: Record<DocumentType, string> = { informe: 'Informe', analitica: 'Analítica', otro: 'Otro' };
const formatter = new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeZone: 'Europe/Madrid' });
function date(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Fecha no disponible' : formatter.format(parsed);
}

function SearchDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const [q, setQ] = useState('');
  const [tipo, setTipo] = useState<DocumentType | ''>('');
  const [criteria, setCriteria] = useState<{ q: string; tipo: DocumentType | '' }>({ q: '', tipo: '' });
  const [page, setPage] = useState<SearchPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const [downloading, setDownloading] = useState<string | null>(null);
  const searchAbort = useRef<AbortController | null>(null);
  const downloadAbort = useRef<AbortController | null>(null);
  const downloadLock = useRef(false);
  useEffect(() => () => { searchAbort.current?.abort(); downloadAbort.current?.abort(); }, []);

  async function search(query: string, type: DocumentType | '', pageNumber: number) {
    searchAbort.current?.abort();
    const abort = new AbortController(); searchAbort.current = abort;
    setLoading(true); setError(''); setPage(null); setCriteria({ q: query, tipo: type });
    try {
      const result = await searchDocuments(query, type, pageNumber, abort.signal);
      if (!abort.signal.aborted) setPage(result);
    } catch (error: unknown) { if (!abort.signal.aborted) setError(errorMessage(error)); }
    finally { if (!abort.signal.aborted) setLoading(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!loading) void search(q.trim(), tipo, 1);
  }
  async function download(document: DocumentItem) {
    if (downloadLock.current || (user.role !== 'patient' && user.role !== 'professional')) return;
    downloadLock.current = true; setDownloading(document.id); setDownloadError('');
    const abort = new AbortController(); downloadAbort.current = abort;
    try {
      const blob = await downloadDocument(document, user.role, user.id, abort.signal);
      if (abort.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement('a');
      link.href = url;
      const extension = { 'application/pdf': 'pdf', 'image/png': 'png', 'image/jpeg': 'jpg' }[blob.type] ?? 'bin';
      link.download = `documento-${document.id}.${extension}`;
      window.document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error: unknown) { if (!abort.signal.aborted) setDownloadError(errorMessage(error)); }
    finally { if (!abort.signal.aborted) { downloadLock.current = false; setDownloading(null); } }
  }
  return <Modal title="Buscar documentos médicos" onClose={onClose}>
    <p className="muted">Busca por descripción o tipo de documento. {user.role === 'patient' ? 'Solo verás tus documentos.' : 'Solo verás documentos de pacientes que comparten sus datos contigo y tienen una cita contigo.'} No se busca dentro de los archivos.</p>
    <form className="document-search-form" onSubmit={submit}>
      <label>Descripción o tipo<input name="q" type="search" autoComplete="off" required minLength={1} maxLength={100} value={q} onChange={(event) => setQ(event.target.value)} /></label>
      <label>Tipo de documento<select value={tipo} onChange={(event) => {
        const value = event.target.value;
        if (value === '' || value === 'informe' || value === 'analitica' || value === 'otro') setTipo(value);
      }}><option value="">Todos</option>{Object.entries(types).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <button className="button primary" type="submit" disabled={loading || !q.trim()}>{loading ? 'Buscando…' : 'Buscar'}</button>
    </form>
    {loading && <p role="status">Buscando documentos…</p>}
    {error && <div role="alert" className="error-state"><p>{error}</p><button className="text-button" onClick={() => { void search(criteria.q, criteria.tipo, 1); }}>Reintentar</button></div>}
    {downloadError && <p className="error-state" role="alert">{downloadError} Puedes volver a intentar la descarga.</p>}
    {page && <section aria-label="Resultados de búsqueda" aria-live="polite">
      <p className="muted">{page.total === 0 ? 'No se han encontrado documentos.' : `${page.total} documentos encontrados.`}</p>
      <ul className="document-results">{page.documents.map((item) => <li key={item.id}>
        <strong>{item.descripcion?.trim() || 'Sin descripción'}</strong><span>{types[item.tipo]} · {date(item.fecha_subida)}</span>
        <button className="text-button" disabled={downloading !== null} onClick={() => { void download(item); }}>{downloading === item.id ? 'Descargando…' : 'Descargar'}</button>
      </li>)}</ul>
      {page.total > page.page_size && <nav className="pagination" aria-label="Páginas de resultados">
        <button disabled={loading || page.page === 1} onClick={() => { void search(criteria.q, criteria.tipo, page.page - 1); }}>Anterior</button>
        <span>Página {page.page} de {Math.ceil(page.total / page.page_size)}</span>
        <button disabled={loading || page.page * page.page_size >= page.total} onClick={() => { void search(criteria.q, criteria.tipo, page.page + 1); }}>Siguiente</button>
      </nav>}
    </section>}
  </Modal>;
}
