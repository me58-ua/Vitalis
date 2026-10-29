import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { destination } from './destination';
import type { User } from '../types/api';

export function RequireRole({ role }: { role: User['role'] }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={destination(user.role)} replace />;
  return <Outlet />;
}
