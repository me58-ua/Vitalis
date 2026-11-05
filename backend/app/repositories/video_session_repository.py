from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import VideoSessionEvent


class VideoSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, event: VideoSessionEvent) -> VideoSessionEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def has_event(self, appointment_id, user_id, event: str) -> bool:
        return self.session.scalar(select(VideoSessionEvent.id).where(
            VideoSessionEvent.appointment_id == appointment_id,
            VideoSessionEvent.user_id == user_id, VideoSessionEvent.event == event,
        ).limit(1)) is not None
