import smtplib
from email.message import EmailMessage

from .config import settings


def send_reset_code(recipient: str, code: str) -> None:
    if not settings.smtp_host:
        # Entorno local: no revelar el código en producción ni devolverlo desde la API.
        print(f"[DESARROLLO] Código de recuperación para {recipient}: {code}")
        return
    message = EmailMessage()
    message["Subject"] = "Código de recuperación - Taller Mecánico"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(f"Su código de recuperación es {code}. Caduca en {settings.reset_code_minutes} minutos.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
