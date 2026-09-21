from sqlalchemy.orm import Session

from app.models import Appointment, ProfessionalSchedule


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

    def rollback(self) -> None:
        self.session.rollback()