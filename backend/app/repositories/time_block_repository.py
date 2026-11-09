from sqlalchemy import select

from app.models import ProfessionalTimeBlock


class TimeBlockRepository:
    def __init__(self, session):
        self.session = session

    def list(self, professional_id, start, end):
        return list(self.session.scalars(select(ProfessionalTimeBlock).where(
            ProfessionalTimeBlock.professional_id == professional_id,
            ProfessionalTimeBlock.start_time < end, ProfessionalTimeBlock.end_time > start,
        ).order_by(ProfessionalTimeBlock.start_time, ProfessionalTimeBlock.id)))

    def get_owned(self, professional_id, block_id):
        return self.session.scalar(select(ProfessionalTimeBlock).where(
            ProfessionalTimeBlock.id == block_id, ProfessionalTimeBlock.professional_id == professional_id))

    def create(self, block):
        self.session.add(block)
        self.session.flush()
        return block

    def delete(self, block):
        self.session.delete(block)
        self.session.flush()
