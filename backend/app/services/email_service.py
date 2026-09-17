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
