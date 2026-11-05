import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import '../../styles/videoconsulta.css';

export function PatientPanelPage() {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  function enter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('');
    try {
      const value = String(new FormData(event.currentTarget).get('consultation_link') ?? '').trim();
      const url = new URL(value, window.location.origin);
      if (url.origin !== window.location.origin || !/^\/patientPanel\/videoconsulta\/[0-9a-f-]{36}\/?$/i.test(url.pathname)) throw new Error();
      navigate(url.pathname);
    } catch { setError('Pega un enlace de videoconsulta de Vitalis facilitado por tu profesional.'); }
  }
  return <main id="contenido" className="role-page section-container"><h1>Página de paciente</h1><section className="patient-video-entry"><h2>Acceder a una videoconsulta</h2><p>Inicia sesión con tu cuenta y pega el enlace que te haya facilitado tu profesional. El servidor comprobará que la cita te pertenece.</p><form onSubmit={enter}><label>Enlace de tu videoconsulta<input name="consultation_link" type="text" required placeholder="Pega aquí el enlace de Vitalis" /></label><button className="button primary" type="submit">Abrir videoconsulta</button>{error && <p role="alert" className="error-state">{error}</p>}</form></section></main>;
}
