from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import EmailStatus, Notification


class NotificationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, notification: Notification) -> Notification:
        self.session.add(notification)
        self.session.flush()
        return notification

    def get(self, notification_id: UUID, recipient_id: UUID) -> Notification | None:
        return self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_id == recipient_id,
            )
        )

    def find_duplicate(
        self, recipient_id: UUID, notification_type: str, entity_id: UUID | None, scheduled_for: datetime | None
    ) -> Notification | None:
        return self.session.scalar(
            select(Notification).where(
                Notification.recipient_id == recipient_id,
                Notification.type == notification_type,
                Notification.entity_id == entity_id,
                Notification.scheduled_for == scheduled_for,
            )
        )

    def list(
        self, recipient_id: UUID, limit: int, unread_only: bool = False, cursor: UUID | None = None
    ) -> list[Notification]:
        query = select(Notification).where(Notification.recipient_id == recipient_id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        if cursor is not None:
            cursor_notification = self.session.get(Notification, cursor)
            if cursor_notification is not None:
                query = query.where(
                    (Notification.created_at < cursor_notification.created_at)
                    | (
                        (Notification.created_at == cursor_notification.created_at)
                        & (Notification.id < cursor_notification.id)
                    )
                )
        return list(
            self.session.scalars(
                query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
            )
        )

    def count_unread(self, recipient_id: UUID) -> int:
        return self.session.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == recipient_id,
                Notification.read_at.is_(None),
            )
        ) or 0

    def find_recent(
        self, recipient_id: UUID, notification_type: str, entity_id: UUID, since: datetime
    ) -> Notification | None:
        return self.session.scalar(
            select(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.type == notification_type,
                Notification.entity_id == entity_id,
                Notification.created_at > since,
            )
            .order_by(Notification.created_at.desc())
            .limit(1)
        )

    def find_recent_by_type(
        self, recipient_id: UUID, notification_type: str, since: datetime
    ) -> Notification | None:
        return self.session.scalar(
            select(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.type == notification_type,
                Notification.created_at >= since,
            )
            .order_by(Notification.created_at.desc())
            .limit(1)
        )

    def mark_read(self, notification: Notification, read_at: datetime | None = None) -> Notification:
        notification.read_at = read_at or datetime.now(timezone.utc)
        self.session.flush()
        return notification

    def mark_all_read(self, recipient_id: UUID, read_at: datetime | None = None) -> int:
        result = self.session.execute(
            update(Notification)
            .where(Notification.recipient_id == recipient_id, Notification.read_at.is_(None))
            .values(read_at=read_at or datetime.now(timezone.utc))
        )
        self.session.flush()
        return result.rowcount

    def due_for_email(self, now: datetime, max_attempts: int = 3, limit: int = 100) -> list[Notification]:
        return list(
            self.session.scalars(
                select(Notification)
                .where(
                    Notification.email_required.is_(True),
                    Notification.email_status.in_((EmailStatus.PENDING, EmailStatus.FAILED)),
                    Notification.scheduled_for <= now,
                    Notification.email_attempts < max_attempts,
                )
                .order_by(Notification.scheduled_for, Notification.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )

    def update_email_result(
        self, notification: Notification, status: EmailStatus, attempts: int, sent_at: datetime | None
    ) -> Notification:
        notification.email_status = status
        notification.email_attempts = attempts
        notification.sent_at = sent_at
        self.session.flush()
        return notification

    def rollback(self) -> None:
        self.session.rollback()
