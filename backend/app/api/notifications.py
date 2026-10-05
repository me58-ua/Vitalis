from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_notification_repository
from app.models import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationResponse,
    ReadAllResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def _response(notification) -> NotificationResponse:
    return NotificationResponse.model_validate(notification, from_attributes=True)


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    current_user: CurrentUser,
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
    unread_only: bool = Query(False),
    cursor: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    notifications = repository.list(current_user.id, limit + 1, unread_only, cursor)
    next_cursor = notifications[limit].id if len(notifications) > limit else None
    return NotificationListResponse(
        notifications=[_response(notification) for notification in notifications[:limit]],
        next_cursor=next_cursor,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    current_user: CurrentUser,
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
):
    return UnreadCountResponse(count=repository.count_unread(current_user.id))


@router.post("/read-all", response_model=ReadAllResponse)
def mark_all_read(
    current_user: CurrentUser,
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
):
    return ReadAllResponse(marked_read=repository.mark_all_read(current_user.id))


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: UUID,
    current_user: CurrentUser,
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
):
    notification = repository.get(notification_id, current_user.id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return _response(repository.mark_read(notification))
