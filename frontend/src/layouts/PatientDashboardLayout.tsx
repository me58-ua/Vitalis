import { useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { DocumentSearch } from '../components/DocumentSearch';
import { Notifications } from '../components/Notifications';
import logo from '../assets/figma/patient/VitaLisLogo.png';
import home from '../assets/figma/patient/Margin1.svg';
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
  if (!user) return null;
  return <div className="patient-dashboard"><a className="skip-link" href="#contenido">Saltar al contenido</a>
    <aside className={`patient-sidebar ${open ? 'is-open' : ''}`} id="patient-navigation"><Link className="patient-brand" to="/"><img src={logo} alt="" />vitaLis</Link>
      <nav aria-label="Navegación del paciente" onClick={() => setOpen(false)}><Link to="/"><img src={home} alt="" />Inicio</Link><Link to="/patientPanel" aria-current={dashboardActive ? 'page' : undefined} className={dashboardActive ? 'active' : undefined}><img src={dashboard} alt="" />Panel de control</Link><Link to="/patientPanel#evaluaciones"><img src={analysis} alt="" />Análisis</Link><Link to="/patientPanel/misCitas"><img src={calendar} alt="" />Mis citas</Link><Link to="/patientPanel/misRecetas" aria-current={prescriptionsActive ? 'page' : undefined} className={prescriptionsActive ? 'active' : undefined}><img src={calendar} alt="" />Mis recetas</Link><Link to="/patientPanel/chats" aria-current={messagesActive ? 'page' : undefined} className={messagesActive ? 'active' : undefined}><img src={messages} alt="" />Mensajes</Link><button onClick={onProfile}><img src={profile} alt="" />Perfil</button></nav>
      <div className="patient-sidebar-bottom"><button disabled={busy} onClick={() => { void logout(); }}><img src={logoutIcon} alt="" />{busy ? 'Cerrando sesión…' : 'Cerrar sesión'}</button>{logoutError && <p role="alert" className="error-state">{logoutError}</p>}</div>
    </aside>
    <div className="patient-dashboard-body"><header className="patient-dashboard-header"><button className="icon-button patient-menu-button" aria-label="Mostrar u ocultar navegación" aria-expanded={open} aria-controls="patient-navigation" onClick={() => setOpen(value => !value)}><img src={menu} alt="" /></button><div className="patient-header-title"><span>Panel del paciente</span><strong>Bienvenido de nuevo, {user.name}</strong></div><div className="patient-header-tools"><DocumentSearch user={user} /><Notifications userId={user.id} /><details className="account-menu"><summary aria-label={`Cuenta de ${user.name}`}><img src={account} alt="" /></summary><div className="account-panel"><strong>{user.name}</strong>{logoutError && <p role="alert">{logoutError}</p>}<button className="text-button" disabled={busy} onClick={() => { void logout(); }}>Cerrar sesión</button></div></details></div></header>{children}</div>
  </div>;
}
