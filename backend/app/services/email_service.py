# Servicio de correo: renderiza plantillas y envía mensajes de bienvenida, citas, contraseñas y notificaciones.
import logging
from email.message import EmailMessage
from pathlib import Path
from smtplib import SMTP

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _render_template(template_name: str, **context: object) -> str:
    template = jinja_env.get_template(template_name)
    return template.render(**context)


def _send_email(recipient: str, subject: str, html_content: str) -> bool:
    smtp_host = settings.SMTP_HOST.strip()
    if not smtp_host:
        logging.info(
            "Skipping email delivery for %s because SMTP_HOST is not configured.",
            recipient,
        )
        return False

    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER.strip()
    smtp_password = settings.SMTP_PASSWORD
    from_email = settings.SMTP_FROM_EMAIL.strip() or smtp_user or "noreply@vitalis.local"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = recipient
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(html_content, subtype="html")

    with SMTP(smtp_host, smtp_port) as smtp_server:
        smtp_server.starttls()
        if smtp_user and smtp_password:
            smtp_server.login(smtp_user, smtp_password)
        smtp_server.send_message(message)

    return True


def send_welcome_email(email: str, name: str) -> None:
    template_context = {
        "name": name,
        "support_email": settings.SMTP_FROM_EMAIL.strip() or "soporte@vitalis.es",
    }
    html_content = _render_template("welcome.html", **template_context)
    _send_email(email, "Bienvenido a Vitalis", html_content)


def send_appointment_confirmation(email: str, appointment_data: dict) -> None:
    appointment = appointment_data or {}
    patient_name = appointment.get("patient_name") or "Paciente"
    time_slot = appointment.get("time") or "tu cita"
    html_content = _render_template(
        "appointment_confirmation.html",
        name=patient_name,
        date=appointment.get("date") or "próximamente",
        time=time_slot,
        location=appointment.get("location") or "nuestra clínica",
    )
    _send_email(email, "Confirmación de cita", html_content)


def send_password_reset_email(email: str, name: str, token: str) -> None:
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    html_content = _render_template(
        "password_reset.html",
        name=name,
        reset_url=reset_url,
        expires_in_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    )
    _send_email(email, "Restablece tu contraseña de Vitalis", html_content)


def send_password_changed_email(email: str, name: str) -> None:
    html_content = _render_template("password_changed.html", name=name)
    _send_email(email, "Contraseña actualizada en Vitalis", html_content)


def send_product_notification_email(email: str, title: str, message: str, link: str | None = None) -> bool:
    """Send only generic product text; callers must not provide clinical content."""
    safe_link = link or settings.FRONTEND_URL.rstrip("/")
    html_content = (
        f"<html><body><h2>{title}</h2><p>{message}</p>"
        f'<p><a href="{safe_link}">Open Vitalis</a></p></body></html>'
    )
    return _send_email(email, title, html_content)
