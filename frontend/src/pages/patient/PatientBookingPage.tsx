import { useCallback, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { bookPatientAppointment, bookingError, getBookingAvailability, getBookingProfessional, type BookingProfessional, type BookingSlot } from '../../api/patientBooking';
import { appointmentTypes } from '../../components/AppointmentSummary';
import { getPatientProfile } from '../../api/patient';
import { useAdminQuery } from '../../hooks/useAdminQuery';
import { addDays, clock, dayLabel, madridDay, mondayOf } from '../../utils/agenda';
import { doctorSelectionPath } from './DoctorSelectionPage';

export function PatientBookingPage() {
  const { professionalId = '' } = useParams();
  const [params] = useSearchParams();
  const modality = params.get('modalidad');
  const load = useCallback((signal: AbortSignal) => getBookingProfessional(professionalId, signal), [professionalId]);
  const state = useAdminQuery(load);

  return <main id="contenido" className="patient-booking">
    <nav className="booking-breadcrumb" aria-label="Ruta de navegación"><Link to="/patientPanel/misCitas">Mis citas</Link><span aria-hidden="true"> / </span><Link to={doctorSelectionPath}>Equipo médico</Link></nav>
    <h1>Reserva tu cita</h1>
    {state.loading && <p role="status">Cargando profesional…</p>}
    {state.error && <div className="error-state" role="alert"><p>{state.error}</p><button className="button secondary" onClick={state.retry}>Reintentar</button></div>}
    {state.data && <BookingForm key={`${state.data.id}/${modality}`} professional={state.data} initialType={modality === 'video' && state.data.telehealth_enabled ? 'video' : 'in_person'} />}
  </main>;
}

function BookingForm({ professional, initialType }: { professional: BookingProfessional; initialType: BookingSlot['type'] }) {
  const today = madridDay();
  const [day, setDay] = useState(today);
  const [month, setMonth] = useState(today.slice(0, 7) + '-01');
  const [type, setType] = useState(initialType);
  const [slot, setSlot] = useState<BookingSlot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sharing, setSharing] = useState<'none' | 'basic' | 'full'>('none');
  const profile = useAdminQuery(getPatientProfile);
  const submitting = useRef(false);
  const navigate = useNavigate();
  const canBook = professional.is_accepting_new_patients && (type === 'in_person' || professional.telehealth_enabled);
  const loadSlots = useCallback((signal: AbortSignal) => canBook
    ? getBookingAvailability(professional.id, { requested_date: day, appointment_type: type }, signal)
    : Promise.resolve(null), [canBook, professional.id, day, type]);
  const availability = useAdminQuery(loadSlots, bookingError);
  const slots = availability.data?.slots.filter(item => item.type === type && Date.parse(item.start_time) > Date.now()) ?? [];
  const selected = slots.find(item => item.start_time === slot?.start_time && item.end_time === slot.end_time);
  const firstCell = mondayOf(month);
  const calendarDays = Array.from({ length: 42 }, (_, index) => addDays(firstCell, index));

  function changeMonth(direction: number) {
    const date = new Date(`${month}T12:00:00Z`);
    date.setUTCMonth(date.getUTCMonth() + direction);
    const nextMonth = date.toISOString().slice(0, 10);
    setMonth(nextMonth);
    selectDay(nextMonth < today ? today : nextMonth);
  }

  function selectDay(value: string) {
    setDay(value);
    setSlot(null);
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canBook || !selected || Date.parse(selected.start_time) <= Date.now() || submitting.current) return;
    const reason = String(new FormData(event.currentTarget).get('reason') ?? '').trim();
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      await bookPatientAppointment({
        professional_id: professional.id, type: selected.type, start_time: selected.start_time,
        end_time: selected.end_time, appointment_reason: reason || null,
        health_sharing: sharing,
      });
      navigate('/patientPanel/misCitas', { replace: true, state: { appointmentBooked: true } });
    } catch (failure) {
      setError(bookingError(failure));
      setSlot(null);
      availability.retry();
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return <form className="booking-form" onSubmit={submit}>
    <section className="booking-panel booking-heading">
      <div><h2>{professional.name}</h2><p>{professional.specialty} · Col. {professional.license_number}</p>
        {type === 'in_person' && professional.practice_address && <p>{professional.practice_address}</p>}</div>
      <fieldset className="booking-modalities" disabled={busy || !professional.is_accepting_new_patients}>
        <legend>Modalidad</legend>
        {(['video', 'in_person'] as const).map(value => <label key={value}>
          <input type="radio" name="modality" value={value} checked={type === value} disabled={value === 'video' && !professional.telehealth_enabled} onChange={() => { setType(value); setSlot(null); setError(''); }} />
          {appointmentTypes[value]}
        </label>)}
      </fieldset>
    </section>
    <div className="booking-calendar-layout">
      <section className="booking-panel">
        <header className="booking-heading">
          <h2 className="booking-month">{dayLabel(month, { month: 'long', year: 'numeric' })}</h2>
          <div className="booking-month-controls">
            <button type="button" className="button secondary" aria-label="Mes anterior" disabled={busy || !canBook || month.slice(0, 7) <= today.slice(0, 7)} onClick={() => changeMonth(-1)}>‹</button>
            <button type="button" className="button secondary" aria-label="Mes siguiente" disabled={busy || !canBook} onClick={() => changeMonth(1)}>›</button>
          </div>
        </header>
        <div className="booking-calendar" role="group" aria-label="Días del mes">
          {calendarDays.slice(0, 7).map(value => <span key={value}>{dayLabel(value, { weekday: 'short' })}</span>)}
          {calendarDays.map(value => value.slice(0, 7) === month.slice(0, 7)
            ? <button key={value} type="button" aria-label={dayLabel(value, { dateStyle: 'full' })} aria-pressed={day === value} disabled={busy || !canBook || value < today} onClick={() => selectDay(value)}>{Number(value.slice(-2))}</button>
            : <span key={value} aria-hidden="true" />)}
        </div>
        <p className="field-help">Zona horaria: Europe/Madrid</p>
      </section>
      <section className="booking-panel">
        <h2>Franjas de atención</h2>
        <p>{dayLabel(day, { dateStyle: 'full' })}</p>
        {!professional.is_accepting_new_patients && <p role="status">Este profesional no acepta nuevos pacientes.</p>}
        {canBook && availability.loading && <p role="status">Cargando horarios…</p>}
        {canBook && availability.error && <div className="error-state" role="alert"><p>{availability.error}</p><button type="button" className="button secondary" onClick={availability.retry}>Reintentar</button></div>}
        {canBook && availability.data && (slots.length ? <div className="booking-slots" role="group" aria-label="Horarios disponibles">{slots.map(item =>
          <button key={`${item.start_time}/${item.end_time}`} type="button" aria-pressed={selected === item} disabled={busy} onClick={() => { setSlot(item); setError(''); }}>{clock(item.start_time)} – {clock(item.end_time)}</button>
        )}</div> : <p role="status">No hay horarios disponibles para esta fecha y modalidad.</p>)}
      </section>
    </div>
    <section className="booking-panel">
      <h2>Resumen de tu cita médica</h2>
      <dl className="booking-summary">
        <div><dt>Profesional</dt><dd>{professional.name}</dd></div>
        <div><dt>Fecha</dt><dd>{dayLabel(day, { dateStyle: 'long' })}</dd></div>
        <div><dt>Horario</dt><dd>{selected ? `${clock(selected.start_time)} – ${clock(selected.end_time)}` : 'Por seleccionar'}</dd></div>
        <div><dt>Modalidad</dt><dd>{appointmentTypes[type]}</dd></div>
      </dl>
      <label>Motivo de consulta (opcional)<textarea name="reason" rows={3} disabled={busy || !canBook} /></label>
      <fieldset className="booking-modalities" disabled={busy || !canBook}>
        <legend>Datos de salud que compartirás con este profesional</legend>
        <label><input type="radio" name="health_sharing" value="none" checked={sharing === 'none'} onChange={() => setSharing('none')} /> No compartir mi perfil de salud</label>
        <label><input type="radio" name="health_sharing" value="basic" checked={sharing === 'basic'} onChange={() => setSharing('basic')} /> Datos básicos (género, edad, altura, peso y hábitos)</label>
        <label><input type="radio" name="health_sharing" value="full" checked={sharing === 'full'} onChange={() => setSharing('full')} /> Perfil completo (incluye medicación, antecedentes familiares, documentos y evaluaciones disponibles)</label>
      </fieldset>
      {profile.data && !profile.data.share_health_data && <p>Tu consentimiento general está desactivado. La opción quedará guardada y se aplicará cuando lo actives.</p>}
      <p>Puedes gestionar el consentimiento general en <Link to="/patientPanel/perfilSalud">Mi perfil de salud</Link>. Tu elección sustituye la anterior para este profesional.</p>
      {error && <p className="error-state" role="alert">{error}</p>}
      <button className="button primary" type="submit" disabled={busy || !canBook || !selected}>{busy ? 'Reservando…' : 'Confirmar cita'}</button>
    </section>
  </form>;
}
