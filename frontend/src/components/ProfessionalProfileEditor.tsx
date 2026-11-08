import { useEffect, useRef, useState, type FormEvent } from 'react';
import { getProfessionalProfile, updateProfessionalProfile } from '../api/professional';
import { professionalError } from '../api/professionalErrors';
import { useAdminQuery } from '../hooks/useAdminQuery';
import { Modal } from './Modal';
import type { ProfessionalProfile, ProfessionalProfileUpdate } from '../types/api';

export const profileFields = {
  specialty: 'Especialidad', license_number: 'Número de colegiación', bio: 'Presentación', practice_address: 'Dirección de consulta',
  practice_phone: 'Teléfono de consulta', default_consultation_duration_minutes: 'Duración de consulta (minutos)',
  is_accepting_new_patients: 'Acepta nuevos pacientes', telehealth_enabled: 'Ofrece teleconsultas',
} as const;
export function profileValue(value: unknown) { return typeof value === 'boolean' ? value ? 'Sí' : 'No' : value == null || value === '' ? 'No indicado' : String(value); }

function ProfileForm({ profile, onBusy, onSaved }: { profile: ProfessionalProfile; onBusy: (busy: boolean) => void; onSaved: () => void }) {
  const values = { ...profile, ...(profile.change_status === 'pending' || profile.change_status === 'rejected' ? profile.pending_changes : {}) };
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (locked.current) return;
    const form = new FormData(event.currentTarget);
    const payload: ProfessionalProfileUpdate = {
      specialty: String(form.get('specialty')).trim(), license_number: String(form.get('license_number')).trim(),
      bio: String(form.get('bio') ?? '').trim() || null, practice_address: String(form.get('practice_address') ?? '').trim() || null,
      practice_phone: String(form.get('practice_phone') ?? '').trim() || null,
      default_consultation_duration_minutes: Number(form.get('default_consultation_duration_minutes')),
      is_accepting_new_patients: form.has('is_accepting_new_patients'), telehealth_enabled: form.has('telehealth_enabled'),
    };
    locked.current = true; setBusy(true); onBusy(true); setError('');
    const abort = new AbortController(); controller.current = abort;
    try { await updateProfessionalProfile(payload, abort.signal); if (!abort.signal.aborted) onSaved(); }
    catch (error: unknown) { if (!abort.signal.aborted) setError(professionalError(error)); }
    finally { locked.current = false; if (!abort.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  return <form className="form-grid" aria-busy={busy} onSubmit={event => { void submit(event); }}>
    <p className="field-help full">Los cambios requieren aprobación administrativa. Tu perfil vigente y tu acceso se mantienen hasta la decisión. Una nueva solicitud reemplaza la pendiente.</p>
    <fieldset className="form-grid full" disabled={busy}>
      <label>Especialidad *<input name="specialty" required maxLength={150} defaultValue={values.specialty ?? profile.specialty} /></label>
      <label>Número de colegiación *<input name="license_number" required maxLength={50} defaultValue={values.license_number ?? profile.license_number} /></label>
      <label className="full">Presentación<textarea name="bio" maxLength={500} defaultValue={values.bio ?? ''} /></label>
      <label className="full">Dirección de consulta<input name="practice_address" maxLength={255} defaultValue={values.practice_address ?? ''} /></label>
      <label>Teléfono de consulta<input name="practice_phone" maxLength={50} defaultValue={values.practice_phone ?? ''} /></label>
      <label>Duración de consulta (minutos) *<input type="number" name="default_consultation_duration_minutes" required min={1} step={1} defaultValue={values.default_consultation_duration_minutes ?? profile.default_consultation_duration_minutes} /></label>
      <label className="checkbox full"><input type="checkbox" name="is_accepting_new_patients" defaultChecked={values.is_accepting_new_patients ?? profile.is_accepting_new_patients} />Acepta nuevos pacientes</label>
      <label className="checkbox full"><input type="checkbox" name="telehealth_enabled" defaultChecked={values.telehealth_enabled ?? profile.telehealth_enabled} />Ofrece teleconsultas</label>
      <button className="button primary full" type="submit">{busy ? 'Enviando…' : 'Enviar cambios a revisión'}</button>
    </fieldset>{error && <p className="error-state full" role="alert">{error}</p>}
  </form>;
}

export function ProfessionalProfileEditor({ onClose }: { onClose: () => void }) {
  const state = useAdminQuery(getProfessionalProfile, professionalError);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const profile = state.data;
  return <Modal title="Perfil profesional" onClose={onClose} busy={busy}>
    {state.loading && <p role="status">Cargando perfil…</p>}
    {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button onClick={state.retry}>Reintentar</button></div>}
    {notice && <p className="success-state" role="status">{notice}</p>}
    {profile && <>
      <h3>Perfil vigente</h3><dl className="professional-profile">{Object.entries(profileFields).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{profileValue(profile[key as keyof typeof profileFields])}</dd></div>)}<dt>Aprobación</dt><dd>{profile.approval_status === 'approved' ? 'Aprobado' : profile.approval_status === 'rejected' ? 'Rechazado' : 'Pendiente'}</dd></dl>
      {profile.change_status === 'pending' && <p role="status">Cambios pendientes de revisión. El perfil vigente sigue publicado.</p>}
      {profile.change_status === 'approved' && <p role="status">La última solicitud fue aprobada.</p>}
      {profile.change_status === 'rejected' && <p className="error-state">Solicitud rechazada: {profile.change_rejection_reason}. Puedes corregirla y volver a enviarla.</p>}
      {profile.pending_changes && <><h3>{profile.change_status === 'rejected' ? 'Últimos cambios rechazados' : 'Cambios solicitados'}</h3><dl>{Object.entries(profile.pending_changes).map(([key, value]) => <div key={key}><dt>{profileFields[key as keyof typeof profileFields]}</dt><dd>{profileValue(value)}</dd></div>)}</dl></>}
      {profile.approval_status === 'approved' && (!editing ? <button className="button primary" onClick={() => { setEditing(true); setNotice(''); }}>Editar perfil</button> : <><ProfileForm key={profile.change_request_id ?? profile.id} profile={profile} onBusy={setBusy} onSaved={() => { setEditing(false); setBusy(false); setNotice('Solicitud enviada al administrador. Los cambios todavía no se han aplicado.'); state.retry(); }} /><button className="button secondary" disabled={busy} onClick={() => setEditing(false)}>Cancelar edición</button></>)}
    </>}
  </Modal>;
}
