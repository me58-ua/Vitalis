import { useCallback } from 'react';
import { getTimeBlocks } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAdminQuery } from './useAdminQuery';

export function useProfessionalTimeBlocks(fromDate: string, toDate: string) {
  const load = useCallback((signal: AbortSignal) => getTimeBlocks(fromDate, toDate, signal), [fromDate, toDate]);
  return useAdminQuery(load, professionalError);
}
