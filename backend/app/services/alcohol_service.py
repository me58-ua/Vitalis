from datetime import date

from app.models import AlcoholLog, User
from app.repositories.alcohol_repository import AlcoholLogRepository
from app.repositories.profile_repository import ProfileRepository


class AlcoholService:
    def __init__(self, logs: AlcoholLogRepository, profiles: ProfileRepository):
        self.logs = logs
        self.profiles = profiles

    def list_history(self, user: User, cursor: int | None, limit: int):
        profile = self.profiles.get_patient(user.id)
        if profile is None:
            raise ValueError("PROFILE_NOT_FOUND")
        return self.logs.list_history(profile.id, cursor, limit)

    def create(self, patient_id, frequency: int, quantity: int | None, binge: int | None, recorded_date: date | None = None):
        if not 0 <= frequency <= 4 or any(value is not None and not 0 <= value <= 4 for value in (quantity, binge)):
            raise ValueError("Alcohol answers must be between 0 and 4")
        if frequency == 0 and (quantity is not None or binge is not None):
            raise ValueError("quantity and binge must be null when frequency is zero")
        if frequency > 0 and (quantity is None or binge is None):
            raise ValueError("quantity and binge are required when frequency is positive")
        return self.logs.create(AlcoholLog(
            patient_id=patient_id, frequency=frequency, quantity=quantity, binge=binge,
            date=recorded_date or date.today(),
        ))
