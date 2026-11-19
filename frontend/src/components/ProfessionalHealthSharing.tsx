import { useEffect, useRef, useState } from 'react';
import { getProfessionalHealthSharing, revokeProfessionalHealthSharing } from '../api/healthProfile';
import { errorMessage } from '../api/errors';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { PatientQueryFeedback } from './PatientDashboardDialogs';

export function ProfessionalHealthSharing({ enabled }: { enabled: boolean }) {
  const state = useAdminQuery(getProfessionalHealthSharing);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function revoke(id: string, name: string) {
    if (request.current) return;
    const abort = new AbortController();
    request.current = abort;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await revokeProfessionalHealthSharing(id, abort.signal);
      if (!abort.signal.aborted) {
        setConfirming(null);
        setNotice(`Se ha retirado el acceso de ${name} a tu perfil de salud.`);
        state.retry();
      }
    } catch (failure: unknown) {
      if (!abort.signal.aborted) setError(errorMessage(failure));
    } finally {
      request.current = null;
      if (!abort.signal.aborted) setSaving(false);
    }
  }

  return <details className="health-sharing-professionals">
    <summary>Qué datos comparto y con quién</summary>
    <PatientQueryFeedback {...state} />
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert" className="error-state">{error}</p>}
    {state.data?.length === 0 && <p>No tienes permisos de acceso guardados para profesionales.</p>}
    {!!state.data?.length && <>
      {!enabled && <p>El consentimiento general está desactivado. Puedes revocar estos permisos guardados mientras el acceso está suspendido.</p>}
      <ul className="health-sharing-list">{state.data.map(item => <li className="health-record" key={item.professional_id}>
        <h3>{item.professional_name}</h3>
        <p><strong>{item.scope === 'basic' ? 'Datos básicos' : 'Perfil completo'}</strong> · {enabled ? 'Acceso activo' : 'Acceso suspendido'}</p>
        <p>Género, edad, altura, peso y hábitos, incluido el consumo de alcohol.</p>
        {item.scope === 'full' && <p>También incluye sexo al nacer, grupo sanguíneo, alergias, condiciones crónicas, medicamentos, antecedentes familiares, documentos de salud y evaluaciones de riesgo disponibles.</p>}
        {confirming === item.professional_id ? <>
          <p>¿Revocar el acceso al perfil para {item.professional_name}? Los diagnósticos y las notas de las citas siguen disponibles en el historial.</p>
          <button type="button" className="button secondary" disabled={saving} onClick={() => { void revoke(item.professional_id, item.professional_name); }}>Confirmar revocación</button>
          <button type="button" className="text-button" disabled={saving} onClick={() => setConfirming(null)}>Cancelar</button>
        </> : <button type="button" className="button secondary" aria-label={`Revocar acceso de ${item.professional_name}`} disabled={saving} onClick={() => { setConfirming(item.professional_id); setError(''); setNotice(''); }}>Revocar acceso</button>}
      </li>)}</ul>
    </>}
  </details>;
}
