import { useState } from 'react';

export function UserAvatar({ name, photoUrl }: { name: string; photoUrl?: string | null }) {
  const [failed, setFailed] = useState(false);
  return <span className="chat-avatar" aria-hidden="true">{photoUrl?.startsWith('https://') && !failed
    ? <img src={photoUrl} alt="" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
    : name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase()}</span>;
}
