import type { User } from '../types/api';

export function destination(role: User['role']): string {
  return role === 'patient' ? '/patientPanel' : role === 'professional' ? '/professionalDashboard' : '/adminPanel';
}
