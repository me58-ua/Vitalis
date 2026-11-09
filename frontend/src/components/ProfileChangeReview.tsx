import { useEffect, useRef, useState } from 'react';
import { decideProfileChange } from '../api/admin';
import { adminUserError } from '../api/adminUserErrors';
import { profileFields, profileValue } from './ProfessionalProfileEditor';
import type { ProfessionalProfile } from '../types/api';

export function ProfileChangeReview({ professionalId, profile, onBusy, onChanged }: { professionalId: string; profile: ProfessionalProfile; onBusy: (busy: boolean) => void; onChanged: (message: string) => void }) {
  const [action, setAction] = useState<'approve' | 'reject' | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  if (profile.change_status !== 'pending' || !profile.pending_changes || !profile.change_request_id) return null;
  async function decide() {
    if (!action || locked.current || !profile.change_request_id) return;
    if (action === 'reject' && !reason.trim()) { setError('Indica el motivo del rechazo.'); return; }
    locked.current = true; setBusy(true); onBusy(true); setError('');
    const abort = new AbortController(); controller.current = abort;
    try {
      await decideProfileChange(professionalId, action === 'approve', { request_id: profile.change_request_id, reason: action === 'reject' ? reason.trim() : null }, abort.signal);
      if (!abort.signal.aborted) onChanged(action === 'approve' ? 'Cambios del perfil aprobados y aplicados.' : 'Solicitud rechazada. El perfil vigente se conserva.');
    } catch (error: unknown) { if (!abort.signal.aborted) setError(adminUserError(error).summary); }
    finally { locked.current = false; if (!abort.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  return <section className="profile-change-review" aria-label="Revisar cambios profesionales"><h3>Cambios de perfil pendientes</h3>
    <p>Compara el perfil vigente con la solicitud. Aprobar no modifica el estado de acceso de la cuenta.</p>
    <dl>{Object.entries(profile.pending_changes).map(([key, value]) => <div key={key}><dt>{profileFields[key as keyof typeof profileFields]}</dt><dd>Vigente: {profileValue(profile[key as keyof typeof profileFields])}<br />Solicitado: <strong>{profileValue(value)}</strong></dd></div>)}</dl>
    {action === 'reject' && <label>Motivo del rechazo *<textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={1000} disabled={busy} required /></label>}
    {action && <p>¿Confirmas {action === 'approve' ? 'la aprobación y aplicación de estos cambios' : 'el rechazo de esta solicitud'}?</p>}
    {error && <p className="error-state" role="alert">{error}</p>}
    <div className="user-form-actions">{action ? <><button className="button primary" disabled={busy} onClick={() => { void decide(); }}>{busy ? 'Guardando…' : 'Confirmar decisión'}</button><button className="button secondary" disabled={busy} onClick={() => { setAction(null); setError(''); }}>Volver</button></> : <><button className="button primary" onClick={() => setAction('approve')}>Aprobar cambios</button><button className="button secondary" onClick={() => setAction('reject')}>Rechazar cambios</button></>}</div>
  </section>;
}
