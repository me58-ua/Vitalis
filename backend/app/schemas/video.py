from datetime import datetime
from pydantic import BaseModel


class VideoJoinResponse(BaseModel):
    domain: str
    room_name: str
    jwt: str
    expires_at: datetime
