import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Notifications } from '../components/Notifications';
import logo from '../../assets/vitalis logo.png';
import dashboard from '../assets/figma/admin/dashboard.svg';
import users from '../assets/figma/admin/manage-users.svg';
import appointments from '../assets/figma/admin/appointments.svg';
import audit from '../assets/figma/admin/audit.svg';
import logoutIcon from '../assets/figma/admin/logout.svg';
import menu from '../assets/figma/admin/menu.svg';
import account from '../assets/figma/admin/account.svg';
import '../styles/admin.css';

export function AdminLayout() {
  const { user, busy, logout, logoutError } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const accountMenu = useRef<HTMLDetailsElement>(null);
  const location = useLocation();
  useEffect(() => {
    if (menuOpen) sidebar.current?.querySelector<HTMLAnchorElement>('a')?.focus();
  }, [menuOpen]);
  useEffect(() => {
    if (accountMenu.current) accountMenu.current.open = false;
  }, [location.pathname]);
  useEffect(() => {
    function dismiss(event: PointerEvent) {
      if (event.target instanceof Node && !accountMenu.current?.contains(event.target) && accountMenu.current) accountMenu.current.open = false;
    }
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape' && accountMenu.current?.open) {
        accountMenu.current.open = false;
        accountMenu.current.querySelector('summary')?.focus();
      }
    }
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('keydown', escape); };
  }, []);
  if (!user) return null;
  const close = () => { setMenuOpen(false); if (menuOpen) menuButton.current?.focus(); };
  return <div className="admin-shell" onKeyDown={(event) => { if (event.key === 'Escape' && menuOpen) close(); }}>
    <a className="skip-link" href="#contenido">Saltar al contenido</a>
    <aside ref={sidebar} id="admin-sidebar" className={`admin-sidebar${menuOpen ? ' is-open' : ''}`}>
      <Link to="/adminPanel" className="admin-brand" aria-label="vitaLis, inicio de administración" onClick={close}><img src={logo} alt="" /><span>vitaLis</span></Link>
      <nav aria-label="Administración"><p className="admin-eyebrow">ADMINISTRACIÓN</p>
        <NavLink to="/adminPanel" end onClick={close}><img src={dashboard} alt="" />Dashboard Admin</NavLink>
        <NavLink to="/adminPanel/gestionUsuarios" onClick={close}><img src={users} alt="" />Gestión de usuarios</NavLink>
        <NavLink to="/adminPanel/gestionCitas" onClick={close}><img src={appointments} alt="" />Gestión de citas</NavLink>
        <NavLink to="/adminPanel/auditoria" onClick={close}><img src={audit} alt="" />Auditoría y logs</NavLink>
      </nav>
    </aside>
    {menuOpen && <button className="admin-menu-backdrop" aria-label="Cerrar menú" onClick={close} />}
    <div className="admin-workspace">
      <header className="admin-header"><div className="admin-header-title">
        <button ref={menuButton} className="icon-button admin-menu-toggle" aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'} aria-expanded={menuOpen} aria-controls="admin-sidebar" onClick={() => setMenuOpen(!menuOpen)}><img src={menu} alt="" /></button>
        <div><p className="admin-eyebrow">PORTAL DE ADMINISTRACIÓN</p><p>Bienvenido, <strong>{user.name}</strong></p></div>
      </div><div className="admin-header-tools"><Notifications key={user.id} userId={user.id} /><details ref={accountMenu} className="account-menu admin-account-menu"><summary className="admin-account" aria-label={`Cuenta de ${user.name}`}><img src={account} alt="" /></summary><div className="account-panel"><strong>{user.name}</strong><span>Administrador</span><p className="field-help">Se cerrarán todas las sesiones de tu cuenta.</p>{logoutError && <p role="alert" className="error-state">{logoutError}</p>}<button className="admin-logout" disabled={busy} onClick={() => { void logout(); }}><img src={logoutIcon} alt="" />{busy ? 'Cerrando sesión…' : 'Cerrar sesión'}</button></div></details></div></header>
      <div key={`${user.id}:${location.pathname}`}><Outlet /></div>
    </div>
  </div>;
}
