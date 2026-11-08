from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AuditAction, ProfessionalSchedule, ProfessionalTimeBlock, Appointment, AppointmentStatus
from app.schemas.working_hours import WorkingHoursCreate
from app.services.audit_service import AuditService
from app.services.appointment_service import AppointmentConflictError, AppointmentNotFoundError


class WorkingHoursService:
    def __init__(self, repository, audits=None):
        self.repository = repository
        self.audit = AuditService(audits)

    def save(self, user, data, schedule_id=None):
        self.repository.lock_owner(user.id)
        row = self.repository.get_owned(user.id, schedule_id) if schedule_id else None
        if schedule_id and row is None:
            raise AppointmentNotFoundError('Working hours not found')
        if row:
            merged = {key: getattr(row, key) for key in WorkingHoursCreate.model_fields}
            merged.update(data.model_dump(exclude_unset=True))
            values = WorkingHoursCreate.model_validate(merged).model_dump()
        else:
            values = data.model_dump()
        if row is None:
            row = ProfessionalSchedule(professional_id=user.id, **values)
        else:
            for key, value in values.items(): setattr(row, key, value)
        try:
            self.repository.save(row)
        except IntegrityError as error:
            self.repository.session.rollback()
            raise AppointmentConflictError('SCHEDULE_OVERLAP') from error
        self.audit.record(user.id, user.role, AuditAction.UPDATE if schedule_id else AuditAction.CREATE, 'professional_schedule', row.id)
        return row

    def delete(self, user, schedule_id):
        self.repository.lock_owner(user.id)
        row = self.repository.get_owned(user.id, schedule_id)
        if row is None: raise AppointmentNotFoundError('Working hours not found')
        self.repository.delete(row)
        self.audit.record(user.id, user.role, AuditAction.DELETE, 'professional_schedule', schedule_id)


class SpontaneousChatAvailabilityService:
    def __init__(self, hours, professionals):
        self.hours = hours
        self.professionals = professionals

    def get(self, professional_id, now=None):
        now = now or datetime.now(timezone.utc)
        result = dict(professional_id=professional_id, evaluated_at=now, timezone='Europe/Madrid', available=False, reason='unavailable', closes_at=None)
        record = self.professionals.get_professional(professional_id)
        if record is None or not record[1].is_accepting_new_patients:
            return result
        local = now.astimezone(ZoneInfo('Europe/Madrid'))
        rows = [row for row in self.hours.list(professional_id, 'chat') if row.is_active and row.day_of_week == local.weekday()
                and row.start_time <= local.time() < row.end_time]
        if not rows:
            return {**result, 'reason': 'outside_hours'}
        db = self.hours.session
        blocked = db.scalar(select(ProfessionalTimeBlock.id).where(ProfessionalTimeBlock.professional_id == professional_id,
                            ProfessionalTimeBlock.start_time <= now, ProfessionalTimeBlock.end_time > now).limit(1))
        if blocked: return {**result, 'reason': 'blocked'}
        busy = db.scalar(select(Appointment.id).where(Appointment.professional_id == professional_id,
                         Appointment.status == AppointmentStatus.CONFIRMED, Appointment.start_time <= now, Appointment.end_time > now).limit(1))
        if busy: return {**result, 'reason': 'busy'}
        closes = min(datetime.combine(local.date(), row.end_time, local.tzinfo) for row in rows)
        return {**result, 'available': True, 'reason': 'available', 'closes_at': closes}
