import { useEffect, useRef, useState, type FormEvent, type InputHTMLAttributes } from 'react';
import { createAdminUser, updateAdminUser } from '../api/admin';
import { adminUserError, userFieldLabels, type UserFormErrors } from '../api/adminUserErrors';
import type { AdminPatientProfile, AdminProfessionalProfile, AdminUserDetail, CreateAdminUser, User } from '../types/api';

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> { name: string; label: string; error?: string }
function Field({ name, label, error, required, ...props }: FieldProps) {
  return <label>{label}{required && ' *'}<input {...props} name={name} required={required} aria-invalid={Boolean(error)} aria-describedby={error ? `error-${name}` : undefined} />{error && <span className="user-field-error" id={`error-${name}`}>{error}</span>}</label>;
}
function validate(form: HTMLFormElement): UserFormErrors {
  const fields: Record<string, string> = {};
  for (const input of form.elements) {
    if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement || input instanceof HTMLSelectElement) || input.disabled || !input.name) continue;
    const label = userFieldLabels[input.name] || input.name;
    if (input.required && !input.value.trim()) fields[input.name] = `${label}: este dato es obligatorio.`;
    else if ('minLength' in input && input.value && input.minLength > 0 && input.value.length < input.minLength) fields[input.name] = `${label}: introduce al menos ${input.minLength} caracteres.`;
    else if (!input.validity.valid) {
      const validity = input.validity;
      if (validity.typeMismatch) fields[input.name] = `${label}: introduce ${input.type === 'email' ? 'un correo electrónico válido' : 'un valor válido'}.`;
      else if (input instanceof HTMLInputElement && validity.rangeUnderflow) fields[input.name] = `${label}: el valor mínimo es ${input.min}.`;
      else if (input instanceof HTMLInputElement && validity.rangeOverflow) fields[input.name] = `${label}: el valor máximo es ${input.max}.`;
      else if ('minLength' in input && validity.tooShort) fields[input.name] = `${label}: introduce al menos ${input.minLength} caracteres.`;
      else if (validity.patternMismatch) fields[input.name] = `${label}: utiliza letras, números, guiones o guiones bajos.`;
      else fields[input.name] = `${label}: revisa el valor introducido.`;
    }
  }
  return { summary: Object.keys(fields).length ? 'No se ha guardado. Revisa los campos indicados.' : '', fields };
}

export function AdminUserForm({ item, initialRole, ownAccount, onBusy, onSaved, onClose }: {
  item?: AdminUserDetail; initialRole: User['role']; ownAccount: boolean; onBusy: (busy: boolean) => void;
  onSaved: (item: AdminUserDetail) => void; onClose: () => void;
}) {
  const [role, setRole] = useState<User['role']>(item?.role ?? initialRole);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<UserFormErrors>({ summary: '', fields: {} });
  const errorRef = useRef<HTMLDivElement>(null);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { if (errors.summary) errorRef.current?.focus(); }, [errors]);
  const patient = item?.patient_profile;
  const professional = item?.professional_profile;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (locked.current) return;
    const form = event.currentTarget;
    const validation = validate(form);
    if (validation.summary) { setErrors(validation); return; }
    const data = new FormData(form);
    const text = (name: string) => String(data.get(name) ?? '').trim();
    const optional = (name: string) => text(name) || null;
    const number = (name: string) => text(name) === '' ? null : Number(text(name));
    const patientProfile: AdminPatientProfile | undefined = role === 'patient' ? {
      address: optional('address'), blood_type: optional('blood_type'), timezone: text('timezone'),
      sex_at_birth: optional('sex_at_birth'), height_cm: number('height_cm'), weight_kg: number('weight_kg'),
    } : undefined;
    const professionalProfile: AdminProfessionalProfile | undefined = role === 'professional' ? {
      specialty: text('specialty'), license_number: text('license_number'), bio: optional('bio'),
      practice_address: optional('practice_address'), practice_phone: optional('practice_phone'),
      default_consultation_duration_minutes: Number(text('default_consultation_duration_minutes')),
      telehealth_enabled: data.has('telehealth_enabled'), is_accepting_new_patients: data.has('is_accepting_new_patients'),
    } : undefined;
    const account = { name: text('name'), dni: text('dni'), username: text('username'), email: text('email'),
      tel: text('tel'), birth_date: text('birth_date'), gender: optional('gender'), role,
      ...(patientProfile ? { patient_profile: patientProfile } : {}),
      ...(professionalProfile ? { professional_profile: professionalProfile } : {}),
    };
    // Passwords are never trimmed, logged, or retained after closing the form.
    const password = String(data.get('password') ?? '');
    locked.current = true; setBusy(true); onBusy(true); setErrors({ summary: '', fields: {} });
    const abort = new AbortController(); controller.current = abort;
    try {
      const payload: CreateAdminUser = { ...account, password };
      const saved = item ? await updateAdminUser(item.id, { ...account, ...(password ? { password } : {}) }, abort.signal)
        : await createAdminUser(payload, abort.signal);
      if (!abort.signal.aborted) onSaved(saved);
    } catch (error: unknown) {
      if (!abort.signal.aborted) setErrors(adminUserError(error, 'save'));
    } finally { locked.current = false; if (!abort.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  const e = errors.fields;
  return <form className="admin-user-form" noValidate aria-busy={busy} onSubmit={event => { void submit(event); }}>
    <p className="field-help">Los campos con * son obligatorios. {role === 'admin' ? 'Las cuentas administradoras no tienen perfil clínico.' : 'La cuenta y el perfil se guardan juntos.'}</p>
    {errors.summary && <div ref={errorRef} role="alert" tabIndex={-1} className="error-state"><strong>{errors.summary}</strong>{Object.keys(e).length > 0 && <ul>{Object.entries(e).map(([key, value]) => <li key={key}>{value}</li>)}</ul>}</div>}
    <fieldset disabled={busy} className="form-grid">
      <h3 className="full">Datos de la cuenta</h3>
      <Field name="name" label="Nombre completo" required maxLength={150} defaultValue={item?.name} error={e.name} autoComplete="off" />
      <label>Tipo de cuenta *<select name="role" value={role} disabled={ownAccount} onChange={event => {
        const value = event.target.value;
        if (value === 'patient' || value === 'professional' || value === 'admin') { setRole(value); setErrors({ summary: '', fields: {} }); }
      }}><option value="patient">Paciente</option><option value="professional">Profesional</option><option value="admin">Administrador</option></select>{ownAccount && <span className="field-help">Gestiona tu rol desde otra cuenta administradora.</span>}</label>
      <Field name="dni" label="DNI / NIE" required minLength={5} maxLength={20} defaultValue={item?.dni} error={e.dni} />
      <Field name="username" label="Nombre de usuario" required minLength={3} maxLength={50} pattern="[\p{L}\p{N}_\-]+" defaultValue={item?.username} error={e.username} autoComplete="off" />
      <Field name="email" label="Correo electrónico" type="email" required maxLength={320} defaultValue={item?.email} error={e.email} />
      <Field name="tel" label="Teléfono" type="tel" required maxLength={32} defaultValue={item?.tel} error={e.tel} />
      <Field name="birth_date" label="Fecha de nacimiento" type="date" required defaultValue={item?.birth_date} error={e.birth_date} />
      <Field name="gender" label="Género (opcional)" maxLength={50} defaultValue={item?.gender ?? ''} error={e.gender} />
      <Field name="password" label={item ? 'Nueva contraseña (déjala vacía para conservarla)' : 'Contraseña'} type="password" autoComplete="new-password" required={!item} minLength={8} maxLength={128} error={e.password} />
      {item && role !== item.role && <p className="user-notice full">El cambio de rol modifica el acceso de esta cuenta. Se creará el perfil correspondiente si falta; los perfiles anteriores se conservarán.</p>}
      {role === 'patient' && <fieldset key="patient" className="form-grid full user-profile-fields" disabled={busy}><legend>Perfil de paciente</legend>
        <Field name="address" label="Dirección (opcional)" maxLength={255} defaultValue={patient?.address ?? ''} error={e.address} />
        <Field name="blood_type" label="Grupo sanguíneo (opcional)" maxLength={10} defaultValue={patient?.blood_type ?? ''} error={e.blood_type} />
        <Field name="height_cm" label="Altura en cm (opcional)" type="number" min={100} max={250} step="any" defaultValue={patient?.height_cm ?? ''} error={e.height_cm} />
        <Field name="weight_kg" label="Peso en kg (opcional)" type="number" min={25} max={400} step="any" defaultValue={patient?.weight_kg ?? ''} error={e.weight_kg} />
        <Field name="sex_at_birth" label="Sexo al nacer (opcional)" maxLength={30} defaultValue={patient?.sex_at_birth ?? ''} error={e.sex_at_birth} />
        <Field name="timezone" label="Zona horaria" required maxLength={50} defaultValue={patient?.timezone ?? 'Europe/Madrid'} error={e.timezone} list="user-timezones" />
        <datalist id="user-timezones"><option value="Europe/Madrid" /><option value="Atlantic/Canary" /><option value="UTC" /></datalist>
        <p className="field-help full">La fecha de nacimiento se comparte con la cuenta. El paciente gestiona sus consentimientos y permisos para compartir datos.</p>
      </fieldset>}
      {role === 'professional' && <fieldset key="professional" className="form-grid full user-profile-fields" disabled={busy}><legend>Perfil profesional</legend>
        <Field name="specialty" label="Especialidad" required maxLength={150} defaultValue={professional?.specialty ?? ''} error={e.specialty} />
        <Field name="license_number" label="Número de colegiación" required maxLength={50} defaultValue={professional?.license_number ?? ''} error={e.license_number} />
        <label className="full">Presentación profesional (opcional)<textarea name="bio" maxLength={500} rows={3} defaultValue={professional?.bio ?? ''} aria-invalid={Boolean(e.bio)} aria-describedby={e.bio ? 'error-bio' : undefined} />{e.bio && <span className="user-field-error" id="error-bio">{e.bio}</span>}</label>
        <Field name="practice_address" label="Dirección de consulta (opcional)" maxLength={255} defaultValue={professional?.practice_address ?? ''} error={e.practice_address} />
        <Field name="practice_phone" label="Teléfono de consulta (opcional)" type="tel" maxLength={50} defaultValue={professional?.practice_phone ?? ''} error={e.practice_phone} />
        <Field name="default_consultation_duration_minutes" label="Duración de consulta (minutos)" type="number" required min={1} step={1} defaultValue={professional?.default_consultation_duration_minutes ?? 30} error={e.default_consultation_duration_minutes} />
        <label className="checkbox full"><input name="is_accepting_new_patients" type="checkbox" defaultChecked={professional?.is_accepting_new_patients ?? true} />Acepta nuevos pacientes</label>
        <label className="checkbox full"><input name="telehealth_enabled" type="checkbox" defaultChecked={professional?.telehealth_enabled ?? true} />Ofrece teleconsultas</label>
        {professional ? <p className="user-notice full">Revisión: {professional.approval_status === 'approved' ? 'aprobado' : professional.approval_status === 'rejected' ? 'rechazado' : 'pendiente'}.{professional.rejection_reason && ` Motivo: ${professional.rejection_reason}`}</p>
          : <p className="user-notice full">El profesional se creará pendiente de aprobación. Tras guardarlo, abre «Gestionar» para revisar y aprobar su perfil.</p>}
      </fieldset>}
      <div className="user-form-actions full"><button className="button primary" type="submit">{busy ? 'Guardando…' : item ? 'Guardar cambios' : role === 'admin' ? 'Crear administrador' : 'Crear usuario y perfil'}</button><button className="button secondary" type="button" onClick={onClose}>Cancelar</button></div>
    </fieldset>
  </form>;
}
