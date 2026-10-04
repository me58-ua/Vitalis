from datetime import date, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentNote, AppointmentStatus, AppointmentStatusHistory, ProfessionalSchedule, User


class AppointmentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_schedule(self, schedule: ProfessionalSchedule) -> ProfessionalSchedule:
        self.session.add(schedule)
        self.session.flush()
        return schedule

    def create_appointment(self, appointment: Appointment) -> Appointment:
        self.session.add(appointment)
        self.session.flush()
        return appointment

    def get_appointment(self, appointment_id: UUID) -> Appointment | None:
        return self.session.get(Appointment, appointment_id)

    def get_schedule(self, schedule_id: UUID) -> ProfessionalSchedule | None:
        return self.session.get(ProfessionalSchedule, schedule_id)

    def list_active_schedules(self, professional_id: UUID, day_of_week: int):
        return list(
            self.session.scalars(
                select(ProfessionalSchedule)
                .where(
                    ProfessionalSchedule.professional_id == professional_id,
                    ProfessionalSchedule.day_of_week == day_of_week,
                    ProfessionalSchedule.is_active.is_(True),
                )
                .order_by(ProfessionalSchedule.start_time)
            )
        )

    def list_booked_appointments(self, professional_id: UUID, start: datetime, end: datetime):
        return list(
            self.session.scalars(
                select(Appointment)
                .where(
                    Appointment.professional_id == professional_id,
                    Appointment.status != AppointmentStatus.CANCELLED,
                    Appointment.start_time < end,
                    Appointment.end_time > start,
                )
            )
        )

    def get_note(self, note_id: UUID) -> AppointmentNote | None:
        return self.session.get(AppointmentNote, note_id)

    def has_shared_appointment(self, patient_id: UUID, professional_id: UUID) -> bool:
        return self.session.scalar(
            select(Appointment.id)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.professional_id == professional_id,
            )
            .limit(1)
        ) is not None

    def list_patient_history(self, patient_id: UUID, professional_id: UUID) -> list[Appointment]:
        return list(
            self.session.scalars(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient_id,
                    Appointment.professional_id == professional_id,
                )
                .order_by(Appointment.start_time.desc())
            )
        )

    def list_patient_notes(self, patient_id: UUID, professional_id: UUID) -> list[AppointmentNote]:
        return list(
            self.session.scalars(
                select(AppointmentNote)
                .join(Appointment, Appointment.id == AppointmentNote.appointment_id)
                .where(
                    Appointment.patient_id == patient_id,
                    Appointment.professional_id == professional_id,
                )
                .order_by(AppointmentNote.created_at.desc())
            )
        )

    def list_past_for_professional(
        self,
        professional_id: UUID,
        now: datetime,
        patient_id: UUID | None,
        patient_search: str | None,
        start: datetime | None,
        end: datetime | None,
        appointment_status: AppointmentStatus | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[Appointment, User]], int]:
        filters = [
            Appointment.professional_id == professional_id,
            Appointment.end_time < now,
        ]
        if patient_id is not None:
            filters.append(Appointment.patient_id == patient_id)
        if patient_search:
            pattern = f"%{patient_search}%"
            filters.append(
                or_(User.name.ilike(pattern), User.username.ilike(pattern), User.email.ilike(pattern))
            )
        if start is not None:
            filters.append(Appointment.start_time >= start)
        if end is not None:
            filters.append(Appointment.start_time < end)
        if appointment_status is not None:
            filters.append(Appointment.status == appointment_status)

        query = (
            select(Appointment, User, AppointmentNote)
            .join(User, User.id == Appointment.patient_id)
            .outerjoin(AppointmentNote, AppointmentNote.appointment_id == Appointment.id)
            .where(and_(*filters))
            .order_by(Appointment.start_time.desc())
            .offset(offset)
            .limit(limit)
        )
        count_query = (
            select(func.count(Appointment.id))
            .join(User, User.id == Appointment.patient_id)
            .where(and_(*filters))
        )
        return list(self.session.execute(query).all()), self.session.scalar(count_query) or 0

    def update_appointment(self, appointment: Appointment, values: dict) -> Appointment:
        for field, value in values.items():
            setattr(appointment, field, value)
        self.session.flush()
        return appointment

    def save(self, appointment: Appointment) -> Appointment:
        self.session.flush()
        return appointment

    def update_schedule(self, schedule: ProfessionalSchedule, values: dict) -> ProfessionalSchedule:
        for field, value in values.items():
            setattr(schedule, field, value)
        self.session.flush()
        return schedule

    def update_note(self, note: AppointmentNote, values: dict) -> AppointmentNote:
        for field, value in values.items():
            setattr(note, field, value)
        self.session.flush()
        return note

    def create_status_history(self, history: AppointmentStatusHistory) -> AppointmentStatusHistory:
        self.session.add(history)
        self.session.flush()
        return history

    def create_note(self, note: AppointmentNote) -> AppointmentNote:
        self.session.add(note)
        self.session.flush()
        return note

    def rollback(self) -> None:
        self.session.rollback()