import { useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import { errorMessage } from '../api/errors';
import { UserAvatar } from './UserAvatar';

export function ProfilePhotoForm() {
  const { user, refreshUser } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const pending = useRef(false);
  if (!user) return null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get('file');
    if (!(file instanceof File) || !file.size) return;
    setSaved(false);
    if (file.size > 5 * 1024 * 1024) { setError('La foto debe pesar como máximo 5 MB.'); return; }
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      await api.put('/users/me/photo', data);
      await refreshUser();
      form.reset();
      setSaved(true);
    } catch (failure) {
      const status = axios.isAxiosError(failure) ? failure.response?.status : undefined;
      setError(status === 413 ? 'La foto supera el tamaño permitido.'
        : status === 422 ? 'Selecciona una imagen JPEG, PNG o WebP válida.' : errorMessage(failure));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return <form className="profile-photo-form" aria-busy={busy} onSubmit={submit}>
    <UserAvatar name={user.name} photoUrl={user.photo_url} />
    <label>Foto de perfil <input type="file" name="file" accept="image/jpeg,image/png,image/webp" required disabled={busy} /></label>
    <button className="button secondary" type="submit" disabled={busy}>{busy ? 'Subiendo…' : 'Guardar foto'}</button>
    {saved && <p role="status">Foto de perfil actualizada.</p>}
    {error && <p role="alert" className="error-state">{error}</p>}
  </form>;
}
