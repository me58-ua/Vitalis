import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { professionalFollowUpPath } from '../api/appointmentFollowUp';
import { completeProfessionalAppointment } from '../api/professional';
import { professionalError } from '../api/professionalErrors';

export function CompleteInPersonAppointment({ appointmentId, professionalId, busy, onBusy }: {
  appointmentId: string;
  professionalId: string;
  busy: boolean;
  onBusy: (busy: boolean) => void;
}) {
  const navigate = useNavigate();
  const pending = useRef<AbortController | null>(null);
  const [error, setError] = useState('');
  useEffect(() => () => pending.current?.abort(), []);

  async function complete() {
    if (busy || pending.current) return;
    const request = new AbortController();
    pending.current = request;
    setError('');
    onBusy(true);
    try {
      await completeProfessionalAppointment(professionalId, appointmentId, request.signal);
      if (!request.signal.aborted) navigate(professionalFollowUpPath(appointmentId));
    } catch (failure) {
      if (!request.signal.aborted) setError(professionalError(failure));
    } finally {
      pending.current = null;
      if (!request.signal.aborted) onBusy(false);
    }
  }

  return <>
    <button className="button primary" type="button" disabled={busy} onClick={() => { void complete(); }}>
      Finalizar cita y abrir seguimiento
    </button>
    {error && <p className="error-state" role="alert">{error}</p>}
  </>;
}
