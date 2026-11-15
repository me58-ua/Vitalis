import { BrowserRouter, Link, Route, Routes, useNavigate } from 'react-router-dom';
import { PatientDashboardLayout } from './layouts/PatientDashboardLayout';
import { AuthProvider } from './auth/AuthProvider';
import { PublicLayout } from './layouts/PublicLayout';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RequireRole } from './auth/RequireRole';
import { PatientPanelPage } from './pages/patient/PatientPanelPage';
import { PatientOnboardingPage } from './pages/patient/PatientOnboardingPage';
import { PatientAppointmentsPage } from './pages/patient/PatientAppointmentsPage';
import { PatientPrescriptionsPage } from './pages/patient/PatientPrescriptionsPage';
import { ProfessionalProfilePage } from './pages/professional/ProfessionalProfilePage';
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
import { VideoConsultationPage } from './pages/VideoConsultationPage';
import { VideoConsultationsIndexPage } from './pages/professional/VideoConsultationsIndexPage';
import { SpontaneousChatsPage } from './pages/SpontaneousChatsPage';

function PatientMessagesPage() {
  const navigate = useNavigate();
  return <PatientDashboardLayout onProfile={() => navigate('/patientPanel')}><SpontaneousChatsPage /></PatientDashboardLayout>;
}

export function App() {
  return <BrowserRouter><AuthProvider><Routes><Route element={<PublicLayout />}>
    <Route path="/" element={<HomePage />} />
    <Route path="/login" element={<LoginPage />} />
    <Route element={<RequireRole role="patient" />}>
      <Route path="/patientPanel/misCitas" element={<PatientAppointmentsPage />} />
      <Route path="/patientPanel/videoconsulta/:appointmentId" element={<VideoConsultationPage />} />
    </Route>
    <Route path="*" element={<main id="contenido" className="not-found section-container"><h1>Página no disponible</h1><Link to="/">Volver al inicio</Link></main>} />
  </Route><Route element={<RequireRole role="patient" />}><Route path="/patientPanel" element={<PatientPanelPage />} /><Route path="/patientPanel/onboarding" element={<PatientOnboardingPage />} /><Route path="/patientPanel/misRecetas" element={<PatientPrescriptionsPage />} /><Route path="/patientPanel/chats" element={<PatientMessagesPage />} /></Route><Route element={<RequireRole role="professional" />}><Route element={<ProfessionalLayout />}>
    <Route path="/professionalDashboard" element={<ProfessionalDashboardPage />} />
    <Route path="/professionalDashboard/misPacientes" element={<MyPatientsPage />} />
    <Route path="/professionalDashboard/perfil" element={<ProfessionalProfilePage />} />
    <Route path="/professionalDashboard/agenda" element={<ProfessionalAgendaPage />} />
    <Route path="/professionalDashboard/chats" element={<SpontaneousChatsPage />} />
    <Route path="/professionalDashboard/videoconsulta" element={<VideoConsultationsIndexPage />} />
    <Route path="/professionalDashboard/videoconsulta/:appointmentId" element={<VideoConsultationPage />} />
  </Route></Route><Route element={<RequireRole role="admin" />}><Route element={<AdminLayout />}>
    <Route path="/adminPanel" element={<AdminPanelPage />} />
    <Route path="/adminPanel/auditoria" element={<AdminAuditPage />} />
    <Route path="/adminPanel/gestionCitas" element={<AdminAppointmentsPage />} />
    <Route path="/adminPanel/gestionUsuarios" element={<AdminUsersPage />} />
  </Route></Route><Route path="/register" element={<RegisterPage />} /></Routes></AuthProvider></BrowserRouter>;
}
