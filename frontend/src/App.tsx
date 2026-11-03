import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthProvider';
import { PublicLayout } from './layouts/PublicLayout';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RequireRole } from './auth/RequireRole';
import { PatientPanelPage } from './pages/patient/PatientPanelPage';
import { ProfessionalDashboardPage } from './pages/professional/ProfessionalDashboardPage';
import { AdminPanelPage } from './pages/admin/AdminPanelPage';
import { RegisterPage } from './pages/RegisterPage';
import { AdminLayout } from './layouts/AdminLayout';
import { AdminAuditPage } from './pages/admin/AdminAuditPage';
import { AdminAppointmentsPage } from './pages/admin/AdminAppointmentsPage';
import { AdminUsersPage } from './pages/admin/AdminUsersPage';
import { ProfessionalLayout } from './layouts/ProfessionalLayout';
import { MyPatientsPage } from './pages/professional/MyPatientsPage';
import { ProfessionalAgendaPage } from './pages/professional/ProfessionalAgendaPage';

export function App() {
  return <BrowserRouter><AuthProvider><Routes><Route element={<PublicLayout />}>
    <Route path="/" element={<HomePage />} />
    <Route path="/login" element={<LoginPage />} />
    <Route element={<RequireRole role="patient" />}>
      <Route path="/patientPanel" element={<PatientPanelPage />} />
    </Route>
    <Route path="*" element={<main id="contenido" className="not-found section-container"><h1>Página no disponible</h1><Link to="/">Volver al inicio</Link></main>} />
  </Route><Route element={<RequireRole role="professional" />}><Route element={<ProfessionalLayout />}><Route path="/professionalDashboard" element={<ProfessionalDashboardPage />} /><Route path="/professionalDashboard/misPacientes" element={<MyPatientsPage />} /><Route path="/professionalDashboard/agenda" element={<ProfessionalAgendaPage />} /></Route></Route><Route element={<RequireRole role="admin" />}><Route element={<AdminLayout />}>
    <Route path="/adminPanel" element={<AdminPanelPage />} />
    <Route path="/adminPanel/auditoria" element={<AdminAuditPage />} />
    <Route path="/adminPanel/gestionCitas" element={<AdminAppointmentsPage />} />
    <Route path="/adminPanel/gestionUsuarios" element={<AdminUsersPage />} />
  </Route></Route><Route path="/register" element={<RegisterPage />} /></Routes></AuthProvider></BrowserRouter>;
}
