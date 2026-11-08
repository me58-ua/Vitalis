import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { approveAdminProfessional, deleteAdminUser, getAdminUser, getAdminUsers, updateAdminUser, getPendingProfileChanges } from '../../api/admin';
import { ProfileChangeReview } from '../../components/ProfileChangeReview';
import { adminUserError } from '../../api/adminUserErrors';
import { useAuth } from '../../auth/AuthContext';
import { AdminUserForm } from '../../components/AdminUserForm';
import { Modal } from '../../components/Modal';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import type { AdminUser, AdminUserDetail, User } from '../../types/api';
import addIcon from '../../assets/figma/admin-users/add.svg';
import searchIcon from '../../assets/figma/admin-users/search.svg';
import previousIcon from '../../assets/figma/admin-users/previous.svg';
import nextIcon from '../../assets/figma/admin-users/next.svg';
import '../../styles/admin-users.css';

const roles: { value: User['role']; label: string }[] = [
  { value: 'patient', label: 'Pacientes' }, { value: 'professional', label: 'Profesionales' }, { value: 'admin', label: 'Administradores' },
];
const describeError = (error: unknown) => adminUserError(error).summary;
function registrationDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Europe/Madrid' }).format(date);
}

function ManageUserDialog({ id, ownId, initialAction = null, onClose, onChanged }: {
  id: string; ownId: string; initialAction?: 'delete' | null; onClose: () => void; onChanged: (message: string, item?: AdminUserDetail) => void;
}) {
  const load = useCallback((signal: AbortSignal) => getAdminUser(id, signal), [id]);
  const state = useAdminQuery(load, describeError);
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState<'delete' | 'activate' | 'deactivate' | 'approve' | null>(initialAction);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const locked = useRef(false);
  useEffect(() => () => controller.current?.abort(), []);
  const item = state.data;
  async function confirm() {
    if (!item || !action || locked.current) return;
    locked.current = true; setBusy(true); setError('');
    const abort = new AbortController(); controller.current = abort;
    try {
      if (action === 'delete') await deleteAdminUser(item.id, abort.signal);
      else if (action === 'approve') await approveAdminProfessional(item.id, abort.signal);
      else await updateAdminUser(item.id, { is_active: action === 'activate' }, abort.signal);
      if (!abort.signal.aborted) onChanged(action === 'delete' ? 'Cuenta eliminada correctamente.' : action === 'approve'
        ? 'Profesional aprobado. Su cuenta está activa.' : action === 'activate' ? 'Cuenta activada correctamente.' : 'Cuenta desactivada correctamente.');
    } catch (error: unknown) { if (!abort.signal.aborted) setError(adminUserError(error, action === 'delete' ? 'delete' : action === 'approve' ? 'approve' : 'save').summary); }
    finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  const needsApproval = item?.role === 'professional' && item.professional_profile?.approval_status !== 'approved';
  return <Modal title={action === 'delete' ? 'Eliminar cuenta' : action === 'approve' ? 'Aprobar profesional' : action ? 'Cambiar acceso' : 'Gestionar usuario'} onClose={onClose} busy={busy}>
    {state.loading && <p role="status" className="user-loading">Cargando cuenta y perfil…</p>}
    {state.error && <div role="alert" className="error-state"><p>{state.error}</p><button className="text-button" onClick={state.retry}>Reintentar</button></div>}
    {item && (action ? <div className="user-confirmation"><p>Cuenta: <strong>{item.name}</strong> (@{item.username}).</p>
      <p>{action === 'delete' ? 'La eliminación es permanente. Si existen registros relacionados, el servidor impedirá eliminar la cuenta.' : action === 'approve'
        ? 'Confirma que has revisado los datos profesionales. Esta acción aprobará el perfil y permitirá iniciar sesión.'
        : action === 'activate' ? 'Esta cuenta volverá a poder iniciar sesión.' : 'Esta cuenta no podrá acceder a la plataforma. Sus datos se conservarán.'}</p>
      {error && <p role="alert" className="error-state">{error}</p>}
      <div className="user-form-actions"><button className={`button ${action === 'delete' ? 'user-danger' : 'primary'}`} disabled={busy} onClick={() => { void confirm(); }}>{busy ? 'Procesando…' : action === 'delete' ? 'Eliminar definitivamente' : 'Confirmar'}</button><button className="button secondary" disabled={busy} onClick={() => { setAction(null); setError(''); }}>Volver</button></div>
    </div> : <>
      <p className="user-detail-id">ID: {item.id}</p>
      {item.professional_profile && <fieldset className="profile-review-fieldset" disabled={busy}><ProfileChangeReview professionalId={item.id} profile={item.professional_profile} onBusy={setBusy} onChanged={onChanged} /></fieldset>}
      <fieldset className="profile-review-fieldset" disabled={busy}><AdminUserForm item={item} initialRole={item.role} ownAccount={item.id === ownId} onBusy={setBusy} onClose={onClose} onSaved={saved => onChanged(saved.role === 'admin' ? 'Cuenta administradora guardada correctamente.' : 'Cuenta y perfil guardados correctamente.', saved)} /></fieldset>
      {item.id !== ownId && <section className="user-account-actions" aria-label="Acceso y eliminación de la cuenta"><h3>Acceso a la plataforma</h3>
        <p>Estado actual: <strong>{item.is_active ? 'Activo' : 'Inactivo'}</strong>.</p>
        {needsApproval && !item.professional_profile && <p className="user-notice">Esta cuenta todavía no tiene perfil profesional. Completa y guarda los campos profesionales antes de aprobarla.</p>}
        <div className="user-form-actions">
          {needsApproval && item.professional_profile && <button className="button secondary" disabled={busy} onClick={() => setAction('approve')}>Aprobar profesional</button>}
          {(item.is_active || !needsApproval) && <button className="button secondary" disabled={busy} onClick={() => setAction(item.is_active ? 'deactivate' : 'activate')}>{item.is_active ? 'Desactivar cuenta' : 'Activar cuenta'}</button>}
          <button className="text-button user-danger-text" disabled={busy} onClick={() => setAction('delete')}>Eliminar cuenta</button>
        </div>
      </section>}
    </>)}
  </Modal>;
}

function CreateUserDialog({ role, onClose, onSaved }: { role: User['role']; onClose: () => void; onSaved: (item: AdminUserDetail) => void }) {
  const [busy, setBusy] = useState(false);
  return <Modal title="Añadir usuario" onClose={onClose} busy={busy}><AdminUserForm initialRole={role} ownAccount={false} onBusy={setBusy} onClose={onClose} onSaved={onSaved} /></Modal>;
}

export function AdminUsersPage() {
  const { user, refreshUser } = useAuth();
  const [role, setRole] = useState<User['role']>('patient');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState({ search: '', page: 1, page_size: 20 });
  const [revision, setRevision] = useState(0);
  const [dialog, setDialog] = useState<'create' | AdminUser | null>(null);
  const [directDelete, setDirectDelete] = useState(false);
  const [success, setSuccess] = useState('');
  const [notice, setNotice] = useState('');
  const load = useCallback((signal: AbortSignal) => {
    void revision;
    return getAdminUsers({ ...query, search: query.search || undefined, role }, signal);
  }, [query, role, revision]);
  const state = useAdminQuery(load, describeError);
  const loadCounts = useCallback(async (signal: AbortSignal) => {
    void revision;
    return Promise.all(roles.map(async ({ value }) => ({ role: value, total: (await getAdminUsers({ role: value, page: 1, page_size: 1 }, signal)).total })));
  }, [revision]);
  const counts = useAdminQuery(loadCounts, describeError);
  const loadChanges = useCallback((signal: AbortSignal) => { void revision; return getPendingProfileChanges(signal); }, [revision]);
  const changes = useAdminQuery(loadChanges, describeError);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const data = state.data;
  function refresh() { setRevision(value => value + 1); }
  async function changed(message: string, item?: AdminUserDetail) {
    setDialog(null); setSuccess(message); setNotice('');
    if (item) { setRole(item.role); setSearch(''); setQuery(value => ({ ...value, search: '', page: 1 })); }
    else setQuery(value => ({ ...value, page: 1 }));
    refresh();
    if (item?.id === user?.id) {
      try { await refreshUser(); }
      catch { setNotice('Los cambios se guardaron, pero no se pudo actualizar tu sesión. Vuelve a iniciar sesión para ver tus datos actualizados.'); }
    }
  }
  function applySearch(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSuccess(''); setQuery({ ...query, search: search.trim(), page: 1 }); }
  if (!user) return null;
  return <main id="contenido" className="admin-main users-main">
    <div className="admin-page-heading users-heading"><div><p className="admin-eyebrow users-eyebrow">ADMINISTRACIÓN</p><h1>Gestión de <em>Usuarios</em></h1><p className="users-intro">Administra los perfiles de pacientes y profesionales, configura sus accesos y mantén sus datos al día.</p></div>
      <div className="users-heading-actions"><button className="button primary user-add" onClick={() => { setSuccess(''); setDialog('create'); }}><img src={addIcon} alt="" />Añadir usuario</button></div>
    </div>
    {success && <p role="status" className="success-state">{success}</p>}
    {notice && <p role="alert" className="error-state">{notice}</p>}
    <section className="users-panel" aria-label="Gestión de usuarios">
      <div className="users-toolbar"><div className="user-role-tabs" role="group" aria-label="Tipo de usuario">{roles.map(tab => <button key={tab.value} aria-pressed={role === tab.value} className={role === tab.value ? 'is-active' : ''} onClick={() => { setRole(tab.value); setQuery(value => ({ ...value, page: 1 })); setSuccess(''); }}>
        {tab.label}<span className="user-count" aria-label={`Total de ${tab.label.toLowerCase()}`}>{counts.loading ? '…' : counts.data?.find(item => item.role === tab.value)?.total ?? '—'}</span>
      </button>)}</div>
        <div className="users-search-tools"><form className="users-search" role="search" onSubmit={applySearch}><label className="sr-only" htmlFor="user-search">Buscar por nombre, correo o usuario</label><img src={searchIcon} alt="" /><input id="user-search" name="search" value={search} onChange={event => setSearch(event.target.value)} maxLength={100} placeholder="Buscar por nombre o email…" /><button type="submit" aria-label="Buscar usuarios">Buscar</button></form></div>
      </div>
      {counts.error && <div className="users-count-error" role="alert"><span>No se pudieron cargar los totales. {counts.error}</span><button className="text-button" onClick={counts.retry}>Reintentar totales</button></div>}
      {role === 'professional' && <section className="profile-change-queue" aria-label="Solicitudes de cambios de perfil"><h2>Perfiles pendientes de revisión</h2>{changes.loading && <p role="status">Cargando solicitudes…</p>}{changes.error && <div className="error-state" role="alert"><p>{changes.error}</p><button onClick={changes.retry}>Reintentar solicitudes</button></div>}{changes.data?.length === 0 && <p>No hay cambios de perfil pendientes.</p>}{changes.data?.map(profile => <p key={profile.id}><strong>{profile.specialty}</strong> · {profile.license_number} <button className="button secondary" onClick={() => setReviewId(profile.user_id)}>Revisar cambios</button></p>)}</section>}
      <div className="users-results" aria-busy={state.loading}>
        {state.loading && <p className="user-list-state" role="status">Cargando usuarios…</p>}
        {state.error && <div className="user-list-state error-state" role="alert"><p>{state.error}</p><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
        {data && (data.users.length ? <table className="users-table"><caption className="sr-only">Cuentas de {roles.find(tab => tab.value === role)?.label.toLowerCase()}. Fechas en Europe/Madrid.</caption><thead><tr><th scope="col">Nombre del usuario</th><th scope="col">Email y contacto</th><th scope="col">Fecha registro</th><th scope="col">Estado</th><th scope="col">Acciones</th></tr></thead><tbody>{data.users.map(item => <tr key={item.id}>
          <th scope="row"><div className="user-name-cell"><span className="user-avatar" aria-hidden="true">{Array.from(item.name.trim().split(/\s+/).slice(0, 2).map(word => Array.from(word)[0] ?? '').join('')).join('').toLocaleUpperCase('es')}</span><div><span className="user-name">{item.name}</span><span className="user-identifier" title={item.id}>ID: {item.id}</span></div></div></th>
          <td data-label="Email y contacto"><span className="user-email">{item.email}</span><span className="user-contact">{item.tel || 'Teléfono no indicado'}</span></td><td data-label="Fecha de registro"><time dateTime={item.created_at}>{registrationDate(item.created_at)}</time></td><td data-label="Estado"><span className={`user-status ${item.is_active ? 'is-active' : 'is-inactive'}`}><span aria-hidden="true" />{item.is_active ? 'Activo' : 'Inactivo'}</span></td><td data-label="Acciones"><div className="user-row-actions"><button className="user-manage" aria-label={`Gestionar a ${item.name}`} onClick={() => { setSuccess(''); setDirectDelete(false); setDialog(item); }}>Gestionar</button><button className="user-delete" aria-label={`Borrar a ${item.name}`} disabled={item.id === user.id} title={item.id === user.id ? 'No puedes borrar tu propia cuenta desde esta sesión.' : undefined} onClick={() => { setSuccess(''); setDirectDelete(true); setDialog(item); }}>Borrar</button></div></td>
        </tr>)}</tbody></table> : <div className="user-list-state"><h2>No se han encontrado usuarios</h2><p>{query.search ? 'Prueba con otro nombre, correo o nombre de usuario.' : 'Todavía no hay cuentas de este tipo.'}</p>{query.search && <button className="text-button" onClick={() => { setSearch(''); setQuery({ ...query, search: '', page: 1 }); }}>Limpiar búsqueda</button>}</div>)}
      </div>
      <footer className="users-footer"><p role="status">{data ? `Mostrando ${data.users.length ? (data.page - 1) * data.page_size + 1 : 0}–${data.users.length ? (data.page - 1) * data.page_size + data.users.length : 0} de ${data.total}` : 'Esperando resultados'}</p>
        <nav className="users-pagination" aria-label="Paginación de usuarios"><button aria-label="Página anterior" disabled={!data || data.page <= 1 || state.loading} onClick={() => setQuery({ ...query, page: query.page - 1 })}><img src={previousIcon} alt="" /></button><span aria-current="page">{query.page}</span><span className="user-page-total">de {data ? Math.max(1, Math.ceil(data.total / data.page_size)) : '…'}</span><button aria-label="Página siguiente" disabled={!data || data.page * data.page_size >= data.total || state.loading} onClick={() => setQuery({ ...query, page: query.page + 1 })}><img src={nextIcon} alt="" /></button></nav>
        <button className="text-button users-refresh" disabled={state.loading} onClick={refresh}>Actualizar lista</button>
      </footer>
    </section>
    {dialog === 'create' && <CreateUserDialog role={role} onClose={() => setDialog(null)} onSaved={item => { void changed(item.role === 'professional' ? 'Cuenta y perfil profesional creados. Pendiente de aprobación: abre «Gestionar» para aprobarlo.' : item.role === 'admin' ? 'Cuenta administradora creada correctamente.' : 'Cuenta y perfil creados correctamente.', item); }} />}
    {dialog && dialog !== 'create' && <ManageUserDialog id={dialog.id} ownId={user.id} initialAction={directDelete ? 'delete' : null} onClose={() => setDialog(null)} onChanged={(message, item) => { void changed(message, item); }} />}
    {reviewId && <ManageUserDialog id={reviewId} ownId={user.id} onClose={() => setReviewId(null)} onChanged={message => { setReviewId(null); void changed(message); }} />}
  </main>;
}
