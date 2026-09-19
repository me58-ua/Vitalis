from dataclasses import dataclass
from datetime import date

from argon2 import PasswordHasher
from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, UserRole


@dataclass(frozen=True)
class SeedUser:
    name: str
    dni: str
    username: str
    email: str
    password: str
    role: UserRole
    tel: str
    birth_date: date
    gender: str | None = None


SEED_USERS = (
    SeedUser("Patient One", "X1234567L", "patient_one", "patient1@vitalis.local", "Patient123!", UserRole.PATIENT, "+34111111111", date(1990, 1, 1), "female"),
    SeedUser("Patient Two", "X1234568L", "patient_two", "patient2@vitalis.local", "Patient123!", UserRole.PATIENT, "+34222222222", date(1988, 2, 2), "male"),
    SeedUser("Professional One", "Y1234567X", "professional_one", "professional1@vitalis.local", "Professional123!", UserRole.PROFESSIONAL, "+34333333333", date(1980, 3, 3), None),
    SeedUser("Professional Two", "Y1234568X", "professional_two", "professional2@vitalis.local", "Professional123!", UserRole.PROFESSIONAL, "+34444444444", date(1982, 4, 4), None),
    SeedUser("Administrator", "Z1234567A", "admin", "admin@vitalis.local", "Admin123!", UserRole.ADMIN, "+34555555555", date(1975, 5, 5), None),
)


def seed_users() -> int:
    password_hasher = PasswordHasher()
    created_count = 0

    with SessionLocal.begin() as session:
        for seed_user in SEED_USERS:
            user = session.scalar(select(User).where(User.email == seed_user.email))
            if user is None:
                session.add(
                    User(
                        name=seed_user.name,
                        dni=seed_user.dni,
                        username=seed_user.username,
                        email=seed_user.email,
                        password_hash=password_hasher.hash(seed_user.password),
                        role=seed_user.role,
                        tel=seed_user.tel,
                        birth_date=seed_user.birth_date,
                        gender=seed_user.gender,
                        is_active=seed_user.role != UserRole.PROFESSIONAL,
                        terms_accepted=True,
                    )
                )
                created_count += 1
            else:
                user.name = seed_user.name
                user.dni = seed_user.dni
                user.username = seed_user.username
                user.tel = seed_user.tel
                user.birth_date = seed_user.birth_date
                user.gender = seed_user.gender
                user.is_active = seed_user.role != UserRole.PROFESSIONAL
                user.terms_accepted = True

    return created_count


if __name__ == "__main__":
    print(f"Created {seed_users()} development users.")