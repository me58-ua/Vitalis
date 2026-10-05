from sqlalchemy.orm import Session

from app.models import VideoSessionEvent


class VideoSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, event: VideoSessionEvent) -> VideoSessionEvent:
        self.session.add(event)
        self.session.flush()
        return event
