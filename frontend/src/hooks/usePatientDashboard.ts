import { useCallback } from 'react';
import { getDashboardAppointments, getPatientProfile, getPatientRisks } from '../api/patient';
import { useAdminQuery } from './useAdminQuery';

export function usePatientDashboard() {
  const profile = useAdminQuery(getPatientProfile);
  const profileId = profile.data?.id;
  const loadRisks = useCallback((signal: AbortSignal) => profileId ? getPatientRisks(profileId, signal) : Promise.resolve(null), [profileId]);
  const risks = useAdminQuery(loadRisks);
  const appointments = useAdminQuery(getDashboardAppointments);
  return { profile, risks, appointments };
}
