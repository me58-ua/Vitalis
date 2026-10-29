import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { destination } from '../auth/destination';
import type { User } from '../types/api';

export function RolePage({ role }: { role: User['role'] }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={destination(user.role)} replace />;
  const messages = { patient: 'Página de paciente', professional: 'Página de profesional', admin: 'Página de admin' };
  return <main id="contenido" className="role-page section-container"><h1>{messages[role]}</h1></main>;
}
