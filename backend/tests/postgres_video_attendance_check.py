"""Exercise attendance and patient listing on PostgreSQL, rolling back all writes."""
from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import Appointment, AppointmentStatus, AppointmentStatusHistory, AppointmentType, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.video_session_repository import VideoSessionRepository
from app.repositories.audit_repository import AuditRepository
from app.services.video_service import VideoService


def check():
    with SessionLocal() as session:
        try:
            appointment = session.scalar(select(Appointment).where(
                Appointment.type == AppointmentType.VIDEO, Appointment.status == AppointmentStatus.CONFIRMED,
            ).order_by(Appointment.start_time).limit(1))
            if appointment is None:
                raise RuntimeError('A confirmed demo video appointment is required')
            patient = session.get(User, appointment.patient_id)
            professional = session.get(User, appointment.professional_id)
            appointments = AppointmentRepository(session)
            events = VideoSessionRepository(session)
            service = VideoService(appointments, events, AuditRepository(session))
            rows, total = appointments.list_patient_appointments(patient.id, 0, 100)
            assert total > 0 and all(session.get(Appointment, row['id']).patient_id == patient.id for row in rows)
            history_query = select(func.count()).select_from(AppointmentStatusHistory).where(AppointmentStatusHistory.appointment_id == appointment.id)
            history_before = session.scalar(history_query)
            for user in (professional, patient):
                service.create_join_session(appointment.id, user)
                service.record_attendance(appointment.id, user, 'joined')
            assert service.record_attendance(appointment.id, patient, 'left')['status'] == AppointmentStatus.COMPLETED
            assert not events.has_event(appointment.id, professional.id, 'left')
            service.record_attendance(appointment.id, patient, 'left')
            service.record_attendance(appointment.id, professional, 'left')
            assert session.scalar(history_query) == history_before + 1
            print('PostgreSQL: patient listing, independent departures, completion, audit/history and idempotency verified; all writes rolled back.')
        finally:
            session.rollback()


if __name__ == '__main__':
    check()
