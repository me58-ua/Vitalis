from dataclasses import dataclass

from argon2 import PasswordHasher
from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, UserRole


@dataclass(frozen=True)
class SeedUser:
    email: str
    password: str
    role: UserRole


SEED_USERS = (
    SeedUser("patient1@vitalis.local", "Patient123!", UserRole.PATIENT),
    SeedUser("patient2@vitalis.local", "Patient123!", UserRole.PATIENT),
    SeedUser("professional1@vitalis.local", "Professional123!", UserRole.PROFESSIONAL),
    SeedUser("professional2@vitalis.local", "Professional123!", UserRole.PROFESSIONAL),
    SeedUser("admin@vitalis.local", "Admin123!", UserRole.ADMIN),
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
                        email=seed_user.email,
                        password_hash=password_hasher.hash(seed_user.password),
                        role=seed_user.role,
                    )
                )
                created_count += 1

    return created_count


if __name__ == "__main__":
    print(f"Created {seed_users()} development users.")