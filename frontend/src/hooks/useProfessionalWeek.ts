import { useCallback } from 'react';
import { getProfessionalWeek } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAdminQuery } from './useAdminQuery';

export function useProfessionalWeek(fromDate: string, toDate: string) {
  const load = useCallback((signal: AbortSignal) => getProfessionalWeek(fromDate, toDate, signal), [fromDate, toDate]);
  return useAdminQuery(load, professionalError);
}
