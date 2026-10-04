from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage


class ChatMessageRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, message: ChatMessage) -> ChatMessage:
        self.session.add(message)
        self.session.flush()
        return message

    def list_by_appointment(
        self,
        appointment_id: UUID,
        limit: int,
        before_id: UUID | None = None,
    ) -> list[ChatMessage]:
        query = select(ChatMessage).where(ChatMessage.appointment_id == appointment_id)
        if before_id is not None:
            before = self.session.get(ChatMessage, before_id)
            if before is not None:
                query = query.where(ChatMessage.sent_at < before.sent_at)
        return list(
            self.session.scalars(
                query.order_by(ChatMessage.sent_at.desc(), ChatMessage.id.desc()).limit(limit)
            )
        )

    def get_after(self, appointment_id: UUID, after_id: UUID) -> list[ChatMessage]:
        after = self.session.get(ChatMessage, after_id)
        if after is None:
            return []
        return list(
            self.session.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.appointment_id == appointment_id,
                    ChatMessage.sent_at > after.sent_at,
                )
                .order_by(ChatMessage.sent_at, ChatMessage.id)
            )
        )
