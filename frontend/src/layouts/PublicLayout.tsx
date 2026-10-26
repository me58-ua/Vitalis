import { Link, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Notifications } from '../components/Notifications';
import logo from '../../assets/vitalis logo.png';
import searchIcon from '../assets/figma/imgMargin.svg';
import accountIcon from '../assets/figma/imgContainer18.svg';

export function PublicLayout() {
  const { user, logout } = useAuth();
  const labels = { patient: 'Paciente', professional: 'Profesional', admin: 'Administrador' };
  return <>
    <a className="skip-link" href="#contenido">Saltar al contenido</a>
    <header className="site-header"><div className="header-inner">
      <Link to="/" className="brand" aria-label="vitaLis, inicio"><img src={logo} alt="vitaLis" /></Link>
      <nav aria-label="Navegación principal" className="main-nav"><Link to="/#servicios">Servicios</Link><Link to="/#privacidad">Privacidad</Link></nav>
      <div className="header-tools">
        <span className="search-unavailable" title="La búsqueda de registros médicos todavía no está disponible.">
          <img src={searchIcon} alt="" /><span>Búsqueda no disponible</span></span>
        {user ? <>
          <Notifications key={user.id} userId={user.id} />
          <details className="account-menu"><summary aria-label={`Cuenta de ${user.name}`}><img src={accountIcon} alt="" /></summary>
            <div className="account-panel"><strong>{user.name}</strong><span>{labels[user.role]}</span>
              <p className="field-help">Cerrar sesión elimina el acceso de esta página. La revocación en el servidor aún no está disponible.</p>
              <button className="text-button" onClick={logout}>Cerrar sesión</button></div>
          </details>
        </> : <Link className="button header-login" to="/?acceso=login">Iniciar sesión</Link>}
      </div>
    </div></header>
    <Outlet />
    <footer className="site-footer"><Link className="footer-brand" to="/">vitaLis<span>Tu salud, mejor comprendida.</span></Link>
      <a href="#privacidad">Privacidad y acceso a tus datos</a></footer>
  </>;
}
