export type Validity = 'valid' | 'soon' | 'expired' | 'unknown' | 'future';

// Calendar dates are compared as days, independently of DST and browser timezone.
export function calendarToday(now = new Date(), timezone = 'Europe/Madrid') {
  let parts: Intl.DateTimeFormatPart[];
  try { parts = new Intl.DateTimeFormat('en', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now); }
  catch { return calendarToday(now, 'Europe/Madrid'); }
  const part = (name: string) => parts.find(item => item.type === name)?.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function prescriptionValidity(item: { fecha_emision?: string | null; fecha_caducidad?: string | null }, today: string): { status: Validity; label: string } {
  if (item.fecha_emision && item.fecha_emision > today) return { status: 'future', label: 'Aún no vigente' };
  if (!item.fecha_caducidad) return { status: 'unknown', label: 'Vigencia no indicada' };
  const remaining = Math.round((Date.parse(`${item.fecha_caducidad}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86400000);
  if (remaining < 0) return { status: 'expired', label: 'Vencida' };
  if (remaining <= 7) return { status: 'soon', label: remaining === 0 ? 'Vence hoy' : remaining === 1 ? 'Expira en 1 día' : `Expira en ${remaining} días` };
  return { status: 'valid', label: 'Vigente' };
}

export function prescriptionDate(value: string | null | undefined) {
  if (!value) return 'No indicada';
  return new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`));
}
