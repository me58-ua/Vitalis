import { Link } from 'react-router-dom';
import '../../styles/videoconsulta.css';

export function PatientPanelPage() {
  return <main id="contenido" className="role-page section-container"><h1>Panel de paciente</h1>
    <section className="patient-video-entry"><h2>Tus citas</h2><p>Consulta tus citas y accede a tu videoconsulta desde tu cuenta.</p>
      <Link className="button primary" to="/patientPanel/misCitas">Ver mis citas</Link>
    </section><section className="patient-video-entry"><h2>Consulta rápida por chat</h2><p>Habla con un médico disponible sin reservar una videoconsulta.</p><Link className="button primary" to="/patientPanel/chats">Abrir chats sin cita</Link></section></main>;
}
