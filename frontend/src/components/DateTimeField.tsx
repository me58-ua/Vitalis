import { useEffect, useRef, useState, type InputHTMLAttributes } from 'react';
import { canonicalValue, localizedValue, type DateTimeKind } from '../utils/dateTime';

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'defaultValue' | 'onChange'> & {
  type: DateTimeKind; value?: string; defaultValue?: string; onValueChange?: (value: string) => void;
};

// Native date/time widgets use the OS/browser locale and can display MM/DD or
// AM/PM. Keep a fixed visible format and canonicalize FormData at its boundary.
export function DateTimeField({ type, value, defaultValue = '', onValueChange, step, ...props }: Props) {
  const seconds = type !== 'date' && Number(step) === 1;
  const [draft, setDraft] = useState({ source: value ?? defaultValue, text: localizedValue(value ?? defaultValue, type, seconds) });
  const display = value !== undefined && value !== draft.source ? localizedValue(value, type, seconds) : draft.text;
  const ref = useRef<HTMLInputElement>(null);
  const format = type === 'date' ? 'DD/MM/AAAA' : type === 'time' ? `HH:mm${seconds ? ':ss' : ''}` : `DD/MM/AAAA HH:mm${seconds ? ':ss' : ''}`;
  useEffect(() => {
    ref.current?.setCustomValidity(display && !canonicalValue(display, type, seconds) ? `Introduce ${format} válido, con horas de 00 a 23.` : '');
  }, [display, type, seconds, format]);
  useEffect(() => {
    const input = ref.current, form = input?.form;
    if (!input || !form) return;
    function convert(event: FormDataEvent) {
      if (input && event.formData.has(input.name) && !input.matches(':disabled')) {
        event.formData.set(input.name, canonicalValue(input.value, type, seconds));
      }
    }
    form.addEventListener('formdata', convert);
    return () => form.removeEventListener('formdata', convert);
  }, [type, seconds, props.name]);
  return <input {...props} ref={ref} type="text" value={display} placeholder={format} title={`Formato: ${format}`} data-date-time-kind={type} data-seconds={seconds ? 'true' : undefined} lang="es-ES" autoCapitalize="off" spellCheck={false}
    onChange={event => {
      let text = event.target.value;
      // Also accept an ISO paste, immediately displaying it in Spanish order.
      if (type !== 'time' && /^\d{4}-\d{2}-\d{2}/.test(text)) text = localizedValue(text, type, seconds);
      const canonical = canonicalValue(text, type, seconds);
      event.target.setCustomValidity(text && !canonical ? `Introduce ${format} válido, con horas de 00 a 23.` : '');
      setDraft({ source: value === undefined ? canonical : canonical || value, text });
      if (canonical || !text) onValueChange?.(canonical);
    }} />;
}
