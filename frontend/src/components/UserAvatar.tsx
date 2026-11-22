import { useState } from 'react';
import { api } from '../api/client';

function photoSource(url: string | null | undefined) {
  if (!url) return undefined;
  if (url.startsWith('https://')) return url;
  if (/^\/assets\/demo-doctor-photos\/[a-z0-9_]+\.jpg$/.test(url)) return url;
  if (/^\/profile-photos\/[a-f0-9-]+\/[a-f0-9-]+\.jpg$/.test(url) && api.defaults.baseURL) return api.defaults.baseURL + url;
  return undefined;
}

export function UserAvatar({ name, photoUrl, fallbackIcon }: { name: string; photoUrl?: string | null; fallbackIcon?: string }) {
  const [failedSource, setFailedSource] = useState<string>();
  const source = photoSource(photoUrl);
  const showPhoto = source && source !== failedSource;
  if (!showPhoto && fallbackIcon) return <img src={fallbackIcon} alt="" />;
  return <span className="chat-avatar" aria-hidden="true">{showPhoto
    ? <img src={source} alt="" referrerPolicy="no-referrer" onError={() => setFailedSource(source)} />
    : name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase()}</span>;
}
