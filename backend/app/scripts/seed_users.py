from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from app.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Appointment, AppointmentStatus, AppointmentType, PatientProfile, ProfessionalPatient,
    ProfessionalProfile, ProfessionalApprovalStatus, User, UserRole,
)


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
    specialty: str | None = None


SEED_USERS = (
    SeedUser("Lucía García Fernández", "X1234567L", "patient_one", "patient1@vitalis.local", "Patient123!", UserRole.PATIENT, "+34111111111", date(1990, 1, 1), "female"),
    SeedUser("Alejandro Martín López", "Y1234567X", "professional_one", "professional1@vitalis.local", "Professional123!", UserRole.PROFESSIONAL, "+34333333333", date(1980, 3, 3), None, "Medicina general"),
    SeedUser("Administrator", "Z1234567A", "admin", "admin@vitalis.local", "Admin123!", UserRole.ADMIN, "+34555555555", date(1975, 5, 5), None),
)

PATIENT_NAMES = (
    ("Carmen Rodríguez Sánchez", "carmen_rodriguez", "female"),
    ("Javier López Martínez", "javier_lopez", "male"),
    ("María González Ruiz", "maria_gonzalez", "female"),
    ("Pablo Fernández Gómez", "pablo_fernandez", "male"),
    ("Elena Pérez Díaz", "elena_perez", "female"),
    ("Diego Sánchez Moreno", "diego_sanchez", "male"),
    ("Ana Romero Jiménez", "ana_romero", "female"),
    ("Sergio Navarro Torres", "sergio_navarro", "male"),
    ("Isabel Molina Serrano", "isabel_molina", "female"),
    ("Álvaro Ortega Rubio", "alvaro_ortega", "male"),
    ("Paula Delgado Castro", "paula_delgado", "female"),
    ("Adrián Ortiz Ramos", "adrian_ortiz", "male"),
    ("Marta Iglesias Gil", "marta_iglesias", "female"),
    ("Daniel Santos Vega", "daniel_santos", "male"),
    ("Sara León Medina", "sara_leon", "female"),
    ("Rubén Herrero Flores", "ruben_herrero", "male"),
    ("Claudia Cabrera Nieto", "claudia_cabrera", "female"),
    ("Hugo Méndez Prieto", "hugo_mendez", "male"),
)
DOCTORS = (
    ("Beatriz Alonso García", "beatriz_alonso", "Cardiología"),
    ("Miguel Hernández Pérez", "miguel_hernandez", "Dermatología"),
    ("Laura Vázquez Romero", "laura_vazquez", "Endocrinología"),
    ("Carlos Serrano Molina", "carlos_serrano", "Neurología"),
    ("Cristina Torres Delgado", "cristina_torres", "Medicina interna"),
)
DEMO_USERS = tuple(
    SeedUser(name, f"DEV-P-{index:04d}", username, f"patient{index + 1}@vitalis.local",
             "Patient123!", UserRole.PATIENT, f"+34000{index:06d}",
             date(1960 + index * 2, index % 12 + 1, index % 27 + 1), gender)
    for index, (name, username, gender) in enumerate(PATIENT_NAMES, start=1)
) + tuple(
    SeedUser(name, f"DEV-M-{index:04d}", username, f"professional{index + 1}@vitalis.local",
             "Professional123!", UserRole.PROFESSIONAL, f"+34001{index:06d}",
             date(1975 + index, index + 1, index + 1), None, specialty)
    for index, (name, username, specialty) in enumerate(DOCTORS, start=1)
)


def _next_slot(session, professional_id, patient_id, candidate):
    """Find a weekday slot without professional or patient overlap (Madrid time)."""
    for _ in range(48 * 366):
        if candidate.weekday() >= 5 or candidate.hour >= 18:
            candidate = datetime.combine(candidate.date() + timedelta(days=1), time(9), candidate.tzinfo)
            continue
        end = candidate + timedelta(minutes=30)
        start_utc, end_utc = candidate.astimezone(timezone.utc), end.astimezone(timezone.utc)
        conflict = session.scalar(select(Appointment.id).where(
            or_(Appointment.professional_id == professional_id, Appointment.patient_id == patient_id),
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < end_utc, Appointment.end_time > start_utc,
        ).limit(1))
        if conflict is None:
            return start_utc, end_utc
        candidate = end
    raise ValueError("No free development appointment slot within one year")


def _seed_past_appointment(session, professional, patient, day, hour, label, reason):
    appointment_id = uuid5(NAMESPACE_URL, f"vitalis-development-appointment:{professional.email}:{patient.email}:{label}")
    if session.get(Appointment, appointment_id) is not None:
        return
    # Stay inside the requested historical day, including weekends for yesterday.
    preferred = (hour - 9) * 2
    for index in range(18):
        slot = (preferred + index) % 18
        start = datetime.combine(day, time(9 + slot // 2, (slot % 2) * 30), ZoneInfo("Europe/Madrid")).astimezone(timezone.utc)
        end = start + timedelta(minutes=30)
        conflict = session.scalar(select(Appointment.id).where(
            or_(Appointment.professional_id == professional.id, Appointment.patient_id == patient.id),
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < end, Appointment.end_time > start,
        ).limit(1))
        if conflict is None:
            session.add(Appointment(
                id=appointment_id, patient_id=patient.id, professional_id=professional.id,
                start_time=start, end_time=end, status=AppointmentStatus.COMPLETED,
                type=AppointmentType.VIDEO, appointment_reason=reason,
                created_at=start - timedelta(days=7), updated_at=end,
            ))
            session.flush()
            return
    raise ValueError("No free appointment slot on the requested historical day")


def _seed_appointments(session, users, now):
    patients = [users[seed.email] for seed in (*SEED_USERS, *DEMO_USERS) if seed.role == UserRole.PATIENT]
    professionals = [users[seed.email] for seed in (*SEED_USERS, *DEMO_USERS) if seed.role == UserRole.PROFESSIONAL]
    today = now.astimezone(ZoneInfo("Europe/Madrid")).date()
    local_day = today + timedelta(days=1)
    previous_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    for professional_index, professional in enumerate(professionals):
        selected = patients if professional_index == 0 else patients[(professional_index - 1) * 3:professional_index * 3]
        for patient_index, patient in enumerate(selected):
            key = f"vitalis-development-appointment:{professional.email}:{patient.email}"
            appointment_id = uuid5(NAMESPACE_URL, key)
            appointment = session.get(Appointment, appointment_id)
            if appointment is None:
                day_offset = patient_index // 5 if professional_index == 0 else 7 + professional_index
                hour = 9 + (patient_index % 5 if professional_index == 0 else patient_index)
                candidate = datetime.combine(local_day + timedelta(days=day_offset), time(hour), ZoneInfo("Europe/Madrid"))
                start, end = _next_slot(session, professional.id, patient.id, candidate)
                appointment = Appointment(
                    id=appointment_id, patient_id=patient.id, professional_id=professional.id,
                    start_time=start, end_time=end,
                    status=AppointmentStatus.CONFIRMED if patient_index % 2 == 0 else AppointmentStatus.PENDING,
                    type=AppointmentType.VIDEO,
                    appointment_reason="Consulta de seguimiento",
                )
                session.add(appointment)
                session.flush()
            elif appointment.appointment_reason == "Consulta de seguimiento (datos sintéticos de desarrollo).":
                # Upgrade only our exact old text, never a manually edited reason.
                appointment.appointment_reason = "Consulta de seguimiento"
            if professional_index == 0 and patient_index < 8:
                _seed_past_appointment(session, professional, patient, today - timedelta(days=1),
                                       9 + patient_index, "yesterday", "Revisión y seguimiento de la consulta anterior")
            if professional_index == 0 and patient_index < 12:
                _seed_past_appointment(session, professional, patient, previous_month.replace(day=5 + patient_index),
                                       10, "last-month", "Consulta de revisión general")
            elif professional_index > 0 and patient_index < 2:
                _seed_past_appointment(session, professional, patient, previous_month.replace(day=20 + professional_index),
                                       10 + patient_index, "last-month", "Consulta de valoración y seguimiento")
            # Derive assignments from an actual booking, never from the user list.
            qualifying = session.scalar(select(Appointment.id).where(
                Appointment.professional_id == professional.id, Appointment.patient_id == patient.id,
                or_(Appointment.status == AppointmentStatus.COMPLETED,
                    (Appointment.start_time >= now) & Appointment.status.in_([
                        AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED,
                    ])),
            ).limit(1))
            if qualifying and session.get(ProfessionalPatient, (professional.id, patient.id)) is None:
                session.add(ProfessionalPatient(professional_id=professional.id, patient_id=patient.id))
                session.flush()


def seed_users(session_factory=SessionLocal, *, include_demo=True, now=None) -> int:
    """Seed development accounts with linked future and historical appointments.

    Re-running repairs account metadata/missing profiles without resetting passwords
    or overwriting an existing patient's profile or clinical information.
    """
    created_count = 0
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Seed time must include a timezone")

    with session_factory.begin() as session:
        users = {}
        seeds = (*SEED_USERS, *DEMO_USERS) if include_demo else SEED_USERS
        for seed_user in seeds:
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
            users[seed_user.email] = user

        session.flush()
        admin = users["admin@vitalis.local"]
        for seed_user in seeds:
            patient = users[seed_user.email]
            if seed_user.role == UserRole.PATIENT and patient.patient_profile is None:
                patient.patient_profile = PatientProfile(
                    birth_date=patient.birth_date, sex_at_birth=seed_user.gender,
                    height_cm=165, weight_kg=62,
                    address="Calle de Pruebas 1, Madrid", blood_type="O+",
                    timezone="Europe/Madrid", onboarding_completed=False,
                    share_health_data=False, ai_processing_consent=False,
                    ai_processing_consent_at=None, family_history_reviewed=False,
                    onboarding_state={},
                )
            professional = users[seed_user.email]
            if seed_user.role == UserRole.PROFESSIONAL and professional.professional_profile is None:
                professional.professional_profile = ProfessionalProfile(
                    specialty=seed_user.specialty,
                    bio=f"Consulta de {seed_user.specialty.lower()} y seguimiento de pacientes.",
                    practice_address="Calle de Pruebas 2, Madrid",
                    practice_phone=professional.tel, license_number=f"DEV-{professional.username}",
                    is_accepting_new_patients=True,
                    default_consultation_duration_minutes=30,
                    telehealth_enabled=True,
                    approval_status=ProfessionalApprovalStatus.APPROVED,
                    rejection_reason=None, reviewed_at=now,
                    reviewed_by=admin.id,
                )
            elif seed_user.role == UserRole.PROFESSIONAL and professional.professional_profile.bio == "Perfil sintético para desarrollo local de Vitalis.":
                professional.professional_profile.bio = f"Consulta de {seed_user.specialty.lower()} y seguimiento de pacientes."
        session.flush()
        if include_demo:
            _seed_appointments(session, users, now)

    return created_count


if __name__ == "__main__":
    print(f"Created {seed_users()} development users.")
