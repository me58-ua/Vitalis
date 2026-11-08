from sqlalchemy import select

from app.models import ProfessionalSchedule, User


class WorkingHoursRepository:
    def __init__(self, session):
        self.session = session

    def lock_owner(self, professional_id):
        return self.session.scalar(select(User).where(User.id == professional_id).with_for_update())

    def list(self, professional_id, channel=None):
        query = select(ProfessionalSchedule).where(ProfessionalSchedule.professional_id == professional_id)
        if channel is not None:
            query = query.where(ProfessionalSchedule.channel == channel)
        return list(self.session.scalars(query.order_by(ProfessionalSchedule.day_of_week, ProfessionalSchedule.start_time, ProfessionalSchedule.id)))

    def get_owned(self, professional_id, schedule_id):
        return self.session.scalar(select(ProfessionalSchedule).where(ProfessionalSchedule.id == schedule_id, ProfessionalSchedule.professional_id == professional_id))

    def save(self, row):
        self.session.add(row)
        self.session.flush()
        return row

    def delete(self, row):
        self.session.delete(row)
        self.session.flush()
