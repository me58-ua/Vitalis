from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.core.security import hash_password
from app.models import PatientProfile, ProfessionalProfile, ProfessionalApprovalStatus, User, UserRole


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
    SeedUser("Professional One", "Y1234567X", "professional_one", "professional1@vitalis.local", "Professional123!", UserRole.PROFESSIONAL, "+34333333333", date(1980, 3, 3), None),
    SeedUser("Administrator", "Z1234567A", "admin", "admin@vitalis.local", "Admin123!", UserRole.ADMIN, "+34555555555", date(1975, 5, 5), None),
)


def seed_users(session_factory=SessionLocal) -> int:
    """Create three development accounts and their profiles; never seed clinical tables.

    Re-running repairs account metadata/missing profiles without resetting passwords
    or overwriting an existing patient's profile or clinical information.
    """
    created_count = 0

    with session_factory.begin() as session:
        users = {}
        for seed_user in SEED_USERS:
            user = session.scalar(select(User).where(User.email == seed_user.email))
            if user is None:
                user = User(
                        name=seed_user.name,
                        dni=seed_user.dni,
                        username=seed_user.username,
                        email=seed_user.email,
                        password_hash=hash_password(seed_user.password),
                        role=seed_user.role,
                        tel=seed_user.tel,
                        birth_date=seed_user.birth_date,
                        gender=seed_user.gender,
                        is_active=True,
                        terms_accepted=True,
                )
                session.add(user)
                created_count += 1
            else:
                user.name = seed_user.name
                user.dni = seed_user.dni
                user.username = seed_user.username
                user.tel = seed_user.tel
                user.birth_date = seed_user.birth_date
                user.gender = seed_user.gender
                if user.role != seed_user.role:
                    raise ValueError("Seed account already exists with a different role")
                user.is_active = True
                user.terms_accepted = True
            users[seed_user.role] = user

        session.flush()
        patient = users[UserRole.PATIENT]
        if patient.patient_profile is None:
            patient.patient_profile = PatientProfile(
                birth_date=patient.birth_date, sex_at_birth="female",
                height_cm=165, weight_kg=62,
                address="Calle de Pruebas 1, Madrid", blood_type="O+",
                timezone="Europe/Madrid", onboarding_completed=False,
                share_health_data=False, ai_processing_consent=False,
                ai_processing_consent_at=None, family_history_reviewed=False,
                onboarding_state={},
            )
        professional = users[UserRole.PROFESSIONAL]
        if professional.professional_profile is None:
            professional.professional_profile = ProfessionalProfile(
                specialty="Medicina general",
                bio="Perfil sintético para desarrollo local de Vitalis.",
                practice_address="Calle de Pruebas 2, Madrid",
                practice_phone=professional.tel, license_number="DEV-000001",
                is_accepting_new_patients=True,
                default_consultation_duration_minutes=30,
                telehealth_enabled=True,
                approval_status=ProfessionalApprovalStatus.APPROVED,
                rejection_reason=None, reviewed_at=datetime.now(timezone.utc),
                reviewed_by=users[UserRole.ADMIN].id,
            )

    return created_count


if __name__ == "__main__":
    print(f"Created {seed_users()} development users.")
