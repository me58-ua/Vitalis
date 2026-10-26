import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { destination } from '../auth/destination';

export function RolePage({ role }: { role: 'patient' | 'professional' }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={destination(user.role)} replace />;
  return <main id="contenido" className="role-page section-container"><h1>{role === 'patient' ? 'Página de paciente' : 'Página de profesional'}</h1></main>;
}
