import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { PatientDashboardLayout } from '../../layouts/PatientDashboardLayout';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { downloadMyPrescription, getMyPrescriptions, getPatientProfile, type PatientPrescription } from '../../api/patient';
import { errorMessage } from '../../api/errors';
import { PatientProfileDialog, PatientQueryFeedback, patientDate } from '../../components/PatientDashboardDialogs';
import { calendarToday, prescriptionDate, prescriptionValidity } from '../../utils/prescriptions';
import medicine from '../../assets/figma/prescriptions/medicine.svg';
import clock from '../../assets/figma/prescriptions/clock.svg';
import info from '../../assets/figma/prescriptions/info.svg';
import downloadIcon from '../../assets/figma/prescriptions/download.svg';
import '../../styles/patient-prescriptions.css';

const typeNames: Record<string, string> = { medicacion: 'Receta de medicación', prueba: 'Solicitud de prueba o procedimiento', otro: 'Otro documento' };
const statusFilters = [['all', 'Todas'], ['active', 'Vigentes'], ['soon', 'Por vencer'], ['expired', 'Vencidas'], ['unknown', 'Sin vigencia']] as const;

function PrescriptionCard({ item, today, timezone }: { item: PatientPrescription; today: string; timezone: string }) {
  const validity = prescriptionValidity(item, today);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function download() {
    if (request.current) return;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError('');
    try {
      const blob = await downloadMyPrescription(item.appointment_id, controller.signal);
      if (controller.signal.aborted) return;
      const suffix = blob.type === 'application/pdf' ? '.pdf' : blob.type === 'image/jpeg' ? '.jpg' : blob.type === 'image/png' ? '.png' : '';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = `receta-${item.id}${suffix}`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason: unknown) {
      if (!controller.signal.aborted) setError(axios.isAxiosError(reason) && reason.response?.status === 404 ? 'El archivo de esta receta no está disponible.' : errorMessage(reason));
    } finally { if (!controller.signal.aborted) { request.current = null; setBusy(false); } }
  }
  return <article className={`patient-prescription-card validity-${validity.status}`} aria-labelledby={`recipe-${item.id}`}>
    <div className="recipe-card-heading"><span className="recipe-document-icon"><img src={validity.status === 'soon' ? clock : medicine} alt="" /></span>
      <div className="recipe-title"><h2 id={`recipe-${item.id}`}>{item.titulo || 'Receta adjunta'}</h2><span className="recipe-type">{typeNames[item.tipo ?? ''] ?? 'Documento adjunto'}</span><span className="recipe-validity">{validity.label}</span></div>
      {item.codigo && <div className="recipe-code"><span>Código del documento</span><strong>{item.codigo}</strong></div>}
    </div>
    <div className="recipe-metadata"><div className="recipe-professional"><span className="recipe-avatar" aria-hidden="true">{item.professional_name.trim().slice(0, 1).toLocaleUpperCase('es')}</span><div><strong>{item.professional_name}</strong><span>Cita del {patientDate(item.appointment_date, timezone)}</span>{item.appointment_reason && <span>{item.appointment_reason}</span>}</div></div>
      <dl className="recipe-dates"><div><dt>Emitida</dt><dd>{item.fecha_emision ? <time dateTime={item.fecha_emision}>{prescriptionDate(item.fecha_emision)}</time> : 'No indicada'}</dd></div><div><dt>Válida hasta</dt><dd>{item.fecha_caducidad ? <time dateTime={item.fecha_caducidad}>{prescriptionDate(item.fecha_caducidad)}</time> : 'No indicada'}</dd></div></dl>
    </div>
    {item.notas && <p className="recipe-notes">{item.notas}</p>}
    <div className="recipe-card-actions"><button className="button primary" disabled={busy} onClick={() => { void download(); }}><img src={downloadIcon} alt="" />{busy ? 'Descargando…' : error ? 'Reintentar descarga' : 'Descargar receta'}</button></div>
    {error && <p className="error-state" role="alert">{error}</p>}
  </article>;
}

export function PatientPrescriptionsPage() {
  const { user } = useAuth();
  return user ? <PatientPrescriptions key={user.id} userId={user.id} /> : null;
}

function PatientPrescriptions({ userId }: { userId: string }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const load = useCallback((signal: AbortSignal) => getMyPrescriptions(userId, signal), [userId]);
  const state = useAdminQuery(load);
  const profile = useAdminQuery(getPatientProfile);
  const [showProfile, setShowProfile] = useState(false);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [type, setType] = useState('');
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const update = () => setNow(new Date());
    const timer = window.setInterval(update, 60000);
    window.addEventListener('focus', update);
    return () => { window.clearInterval(timer); window.removeEventListener('focus', update); };
  }, []);
  const timezone = profile.data?.timezone ?? 'Europe/Madrid';
  const today = calendarToday(now, timezone);
  const items = state.data?.prescriptions ?? [];
  const soon = items.filter(item => prescriptionValidity(item, today).status === 'soon');
  const firstSoon = soon[0];
  const matchesStatus = (item: PatientPrescription, selected: string) => {
    const status = prescriptionValidity(item, today).status;
    return selected === 'all' || (selected === 'active' ? status === 'valid' || status === 'soon' : status === selected);
  };
  const query = search.trim().toLocaleLowerCase('es');
  const visible = items.filter(item => matchesStatus(item, filter) && (!type || item.tipo === type) && (!query || [item.titulo, item.professional_name, item.codigo].some(value => value?.toLocaleLowerCase('es').includes(query))));
  return <PatientDashboardLayout onProfile={() => { if (profile.data) setShowProfile(true); else navigate('/patientPanel'); }}><main id="contenido" className="patient-prescriptions-main">
    <header className="recipes-heading"><p className="recipes-eyebrow"><span>Portal del paciente</span><span aria-hidden="true">/</span>Documentación clínica</p><h1>Mis recetas médicas</h1><p>Consulta y descarga las recetas y solicitudes de pruebas de tus profesionales de la salud.</p></header>
    <PatientQueryFeedback {...state} />
    {state.data && <>
      {firstSoon && <aside className="recipe-expiry-banner" aria-label="Vencimiento cercano"><span className="recipe-info-icon"><img src={info} alt="" /></span><div><strong>{soon.length === 1 ? '1 receta requiere atención pronto' : `${soon.length} recetas requieren atención pronto`}</strong><span className="recipe-banner-badge">Vencimiento cercano</span><p>{soon.length === 1 ? `${firstSoon.titulo || 'Tu receta'}: ${prescriptionValidity(firstSoon, today).label.toLocaleLowerCase('es')}.` : 'Estas recetas vencen hoy o en los próximos 7 días.'}</p></div></aside>}
      <section className="recipe-filters" aria-label="Filtrar recetas"><div className="recipe-status-filters">{statusFilters.map(([value, label]) => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label} <span>({items.filter(item => matchesStatus(item, value)).length})</span></button>)}</div>
        <div className="recipe-search-filters"><label><span>Buscar recetas</span><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Medicamento, profesional o código…" /></label><label><span>Tipo de documento</span><select value={type} onChange={event => setType(event.target.value)}><option value="">Todos los tipos</option>{Object.entries(typeNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
      </section>
      <p className="recipe-result-count" role="status">{visible.length} de {items.length} {items.length === 1 ? 'receta' : 'recetas'}</p>
      {visible.length ? <div className="patient-prescription-list">{visible.map(item => <PrescriptionCard key={item.id} item={item} today={today} timezone={timezone} />)}</div> : <div className="patient-empty"><h2>{items.length ? 'No hay recetas para estos filtros' : 'Todavía no tienes recetas'}</h2><p>{items.length ? 'Prueba con otro nombre, estado o tipo de documento.' : 'Cuando tu profesional adjunte una receta a una cita finalizada, podrás consultarla y descargarla aquí.'}</p>{items.length > 0 && <button className="text-button" onClick={() => { setSearch(''); setType(''); setFilter('all'); }}>Limpiar filtros</button>}</div>}
    </>}
  </main>{showProfile && user && profile.data && <PatientProfileDialog user={user} profile={profile.data} onClose={() => setShowProfile(false)} />}</PatientDashboardLayout>;
}
