from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentStatusHistory, AppointmentNote, ProfessionalSchedule


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

    def get_note(self, note_id: UUID) -> AppointmentNote | None:
        return self.session.get(AppointmentNote, note_id)

    def update_appointment(self, appointment: Appointment, values: dict) -> Appointment:
        for field, value in values.items():
            setattr(appointment, field, value)
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