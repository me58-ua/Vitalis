import { useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Notifications } from '../components/Notifications';
import logo from '../../assets/vitalis logo.png';
import dashboard from '../assets/figma/professional/nav-dashboard.svg';
import agenda from '../assets/figma/professional/nav-agenda.svg';
import patients from '../assets/figma/professional/nav-patients.svg';
import video from '../assets/figma/professional/nav-video.svg';
import chat from '../assets/figma/professional/nav-chat.svg';
import profile from '../assets/figma/professional/nav-profile.svg';
import menu from '../assets/figma/admin/menu.svg';
import account from '../assets/figma/admin/account.svg';
import logoutIcon from '../assets/figma/admin/logout.svg';
import '../styles/admin.css';
import '../styles/professional.css';

export function ProfessionalLayout() {
  const { user, busy, logout, logoutError } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const accountMenu = useRef<HTMLDetailsElement>(null);
  const location = useLocation();
  const panel = new URLSearchParams(location.search).get('panel');
  useEffect(() => { if (menuOpen) sidebar.current?.querySelector<HTMLAnchorElement>('a')?.focus(); }, [menuOpen]);
  useEffect(() => {
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && accountMenu.current && !accountMenu.current.contains(event.target)) accountMenu.current.open = false;
    }
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape' && accountMenu.current?.open) { accountMenu.current.open = false; accountMenu.current.querySelector('summary')?.focus(); }
    }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, []);
  const close = () => { setMenuOpen(false); if (menuOpen) menuButton.current?.focus(); };
  if (!user) return null;
  return <div className="admin-shell professional-shell" onKeyDown={event => { if (event.key === 'Escape' && menuOpen) close(); }}>
    <a className="skip-link" href="#contenido">Saltar al contenido</a>
    <aside ref={sidebar} id="professional-sidebar" className={`admin-sidebar${menuOpen ? ' is-open' : ''}`}>
      <Link to="/professionalDashboard" className="admin-brand" onClick={close} aria-label="vitaLis, inicio profesional"><img src={logo} alt="" /><span>vitaLis</span></Link>
      <nav aria-label="Portal profesional"><p className="admin-eyebrow">PROFESIONAL</p>
        <Link to="/professionalDashboard" className={location.pathname === '/professionalDashboard' && !panel ? 'active' : ''} onClick={close}><img src={dashboard} alt="" />Panel del profesional</Link>
        <Link to="/professionalDashboard/agenda" className={location.pathname === '/professionalDashboard/agenda' ? 'active' : ''} onClick={close}><img src={agenda} alt="" />Agenda</Link>
        <Link to="/professionalDashboard/misPacientes" className={location.pathname === '/professionalDashboard/misPacientes' ? 'active' : ''} onClick={close}><img src={patients} alt="" />Mis pacientes</Link>
        <Link to="/professionalDashboard/videoconsulta" className={location.pathname.startsWith('/professionalDashboard/videoconsulta') ? 'active' : ''} onClick={close}><img src={video} alt="" />Videoconsulta</Link>
        <Link to="/professionalDashboard/chats" className={location.pathname === '/professionalDashboard/chats' ? 'active' : ''} onClick={close}><img src={chat} alt="" />Mensajes</Link>
        <Link to="/professionalDashboard/perfil" className={location.pathname === '/professionalDashboard/perfil' ? 'active' : ''} onClick={close}><img src={profile} alt="" />Perfil profesional</Link>
      </nav>
    </aside>
    {menuOpen && <button className="admin-menu-backdrop" aria-label="Cerrar menú" onClick={close} />}
    <div className="admin-workspace"><header className="admin-header professional-header"><div className="admin-header-title">
      <button ref={menuButton} className="icon-button admin-menu-toggle" aria-expanded={menuOpen} aria-controls="professional-sidebar" aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'} onClick={() => setMenuOpen(!menuOpen)}><img src={menu} alt="" /></button>
      <div><p className="admin-eyebrow">PORTAL PROFESIONAL</p><p>Bienvenido, <strong>{user.name}</strong></p></div>
    </div><div className="admin-header-tools"><Notifications key={`${user.id}:notifications`} userId={user.id} />
      <details ref={accountMenu} className="account-menu admin-account-menu"><summary className="admin-account" aria-label={`Cuenta de ${user.name}`}><img src={account} alt="" /></summary><div className="account-panel"><strong>{user.name}</strong><span>Profesional</span>{logoutError && <p className="error-state" role="alert">{logoutError}</p>}<button className="professional-logout admin-logout" disabled={busy} onClick={() => { void logout(); }}><img src={logoutIcon} alt="" />{busy ? 'Cerrando sesión…' : 'Cerrar sesión'}</button></div></details>
    </div></header><div key={user.id}><Outlet /></div></div>
  </div>;
}
