from sqlalchemy import select, func, or_, tuple_
from app.models import SpontaneousChat, SpontaneousChatMessage, User


class SpontaneousChatRepository:
    def __init__(self, session): self.session = session

    def get(self, chat_id, lock=False):
        query = select(SpontaneousChat).where(SpontaneousChat.id == chat_id)
        if lock: query = query.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(query)

    def open_for_pair(self, patient_id, professional_id):
        return self.session.scalar(select(SpontaneousChat).where(SpontaneousChat.patient_id == patient_id,
                                   SpontaneousChat.professional_id == professional_id, SpontaneousChat.status == 'open'))

    def list(self, user_id, offset, limit):
        owned = or_(SpontaneousChat.patient_id == user_id, SpontaneousChat.professional_id == user_id)
        total = self.session.scalar(select(func.count()).select_from(SpontaneousChat).where(owned)) or 0
        rows = list(self.session.scalars(select(SpontaneousChat).where(owned).order_by(SpontaneousChat.updated_at.desc(), SpontaneousChat.id.desc()).offset(offset).limit(limit)))
        return rows, total

    def save(self, item):
        self.session.add(item)
        self.session.flush()
        return item

    def names(self, chat):
        return {row.id: row.name for row in self.session.scalars(select(User).where(User.id.in_([chat.patient_id, chat.professional_id])))}

    def existing_message(self, chat_id, sender_id, client_id):
        return self.session.scalar(select(SpontaneousChatMessage).where(SpontaneousChatMessage.chat_id == chat_id, SpontaneousChatMessage.sender_id == sender_id, SpontaneousChatMessage.client_id == client_id))

    def message(self, chat_id, message_id):
        return self.session.scalar(select(SpontaneousChatMessage).where(SpontaneousChatMessage.chat_id == chat_id, SpontaneousChatMessage.id == message_id))

    def messages(self, chat_id, limit, before=None, after=None):
        query = select(SpontaneousChatMessage).where(SpontaneousChatMessage.chat_id == chat_id)
        cursor = before or after
        if cursor:
            boundary = self.message(chat_id, cursor)
            if boundary is None: raise ValueError('CHAT_CURSOR_INVALID')
            key = tuple_(SpontaneousChatMessage.created_at, SpontaneousChatMessage.id)
            query = query.where(key < (boundary.created_at, boundary.id) if before else key > (boundary.created_at, boundary.id))
        order = (SpontaneousChatMessage.created_at, SpontaneousChatMessage.id)
        query = query.order_by(*(column.asc() if after else column.desc() for column in order))
        rows = list(self.session.scalars(query.limit(limit + 1)))
        more = len(rows) > limit
        return (rows[:limit] if after else list(reversed(rows[:limit]))), more
