import { useEffect, useState } from 'react';
import { errorMessage } from '../api/errors';

export function useAdminQuery<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{
    load: typeof load; revision: number; data: T | null; error: string;
  } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then((data) => {
      if (!controller.signal.aborted) setResult({ load, revision, data, error: '' });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setResult({ load, revision, data: null, error: errorMessage(error) });
    });
    return () => controller.abort();
  }, [load, revision]);
  const current = result?.load === load && result.revision === revision ? result : null;
  return { data: current?.data ?? null, error: current?.error ?? '', loading: !current, retry: () => setRevision((value) => value + 1) };
}
