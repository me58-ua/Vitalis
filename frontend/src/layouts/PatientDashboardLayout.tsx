import { UserAvatar } from '../components/UserAvatar';
import { useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { appointmentHistoryPath } from '../api/appointmentFollowUp';
import { Notifications } from '../components/Notifications';
import { doctorSelectionPath } from '../pages/patient/DoctorSelectionPage';
import logo from '../assets/vitalis-logo.png';
import dashboard from '../assets/figma/patient/Margin2.svg';
import analysis from '../assets/figma/patient/Margin3.svg';
import calendar from '../assets/figma/patient/Margin4.svg';
import messages from '../assets/figma/patient/Margin5.svg';
import profile from '../assets/figma/patient/Margin6.svg';
import logoutIcon from '../assets/figma/patient/Margin7.svg';
import menu from '../assets/figma/patient/Container11.svg';
import account from '../assets/figma/patient/Container13.svg';
import '../styles/patient-dashboard.css';

export function PatientDashboardLayout({ children, onProfile }: { children: ReactNode; onProfile: () => void }) {
  const { user, busy, logout, logoutError } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const messagesActive = location.pathname.endsWith('/chats');
  const prescriptionsActive = location.pathname.endsWith('/misRecetas');
  const dashboardActive = location.pathname === '/patientPanel';
  const historyActive = location.pathname === appointmentHistoryPath || location.pathname.startsWith('/patientPanel/misCitas/');
  if (!user) return null;
  return <div className="patient-dashboard"><a className="skip-link" href="#contenido">Saltar al contenido</a>
    <aside className={`patient-sidebar ${open ? 'is-open' : ''}`} id="patient-navigation"><Link className="patient-brand" to="/patientPanel" aria-label="vitaLis, panel del paciente"><img src={logo} alt="" />vitaLis</Link>
      <nav aria-label="Navegación del paciente" onClick={() => setOpen(false)}>
        <Link to="/patientPanel" aria-current={dashboardActive ? 'page' : undefined} className={dashboardActive ? 'active' : undefined}><img src={dashboard} alt="" />Panel de control</Link>
        <Link to="/patientPanel/perfilSalud" aria-current={(location.pathname.includes('/onboarding') || location.pathname.endsWith('/perfilSalud')) ? 'page' : undefined} className={(location.pathname.includes('/onboarding') || location.pathname.endsWith('/perfilSalud')) ? 'active' : undefined}><img src={analysis} alt="" />Mi perfil de salud</Link>
        <Link to="/patientPanel#evaluaciones"><img src={analysis} alt="" />Análisis</Link>
        <NavLink to={doctorSelectionPath}><img src={calendar} alt="" />Pedir cita</NavLink>
        <NavLink to="/patientPanel/misCitas" end><img src={calendar} alt="" />Mis próximas citas</NavLink>
        <Link to={appointmentHistoryPath} className={historyActive ? 'active' : undefined} aria-current={historyActive ? 'page' : undefined}><img src={calendar} alt="" />Historial</Link>
        <Link to="/patientPanel/misRecetas" aria-current={prescriptionsActive ? 'page' : undefined} className={prescriptionsActive ? 'active' : undefined}><img src={calendar} alt="" />Mis recetas</Link>
        <Link to="/patientPanel/chats" aria-current={messagesActive ? 'page' : undefined} className={messagesActive ? 'active' : undefined}><img src={messages} alt="" />Chat médico</Link>
        <button onClick={onProfile}><img src={profile} alt="" />Perfil</button>
      </nav>
      <div className="patient-sidebar-bottom"><button disabled={busy} onClick={() => { void logout(); }}><img src={logoutIcon} alt="" />{busy ? 'Cerrando sesión…' : 'Cerrar sesión'}</button>{logoutError && <p role="alert" className="error-state">{logoutError}</p>}</div>
    </aside>
    <div className="patient-dashboard-body"><header className="patient-dashboard-header"><button className="icon-button patient-menu-button" aria-label="Mostrar u ocultar navegación" aria-expanded={open} aria-controls="patient-navigation" onClick={() => setOpen(value => !value)}><img src={menu} alt="" /></button><div className="patient-header-title"><span>Panel del paciente</span><strong>Bienvenido de nuevo, {user.name}</strong></div><div className="patient-header-tools"><Notifications userId={user.id} /><details className="account-menu"><summary aria-label={`Cuenta de ${user.name}`}><UserAvatar name={user.name} photoUrl={user.photo_url} fallbackIcon={account} /></summary><div className="account-panel"><strong>{user.name}</strong>{logoutError && <p role="alert">{logoutError}</p>}<button className="text-button" disabled={busy} onClick={() => { void logout(); }}>Cerrar sesión</button></div></details></div></header>{children}</div>
  </div>;
}
