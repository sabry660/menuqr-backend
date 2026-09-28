"""Email abstraction. Dev uses a console provider that just logs; production can
switch EMAIL_PROVIDER=smtp. Tests should monkeypatch `send` to a no-op/spy so we
NEVER send real emails during pytest runs (see tests/conftest.py).
"""
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class EmailMessage:
    def __init__(self, to: str, subject: str, body: str):
        self.to = to
        self.subject = subject
        self.body = body


async def _console_send(message: EmailMessage) -> None:
    logger.info("email.console_send", to=message.to, subject=message.subject)
    print(f"\n--- [DEV EMAIL] To: {message.to} | Subject: {message.subject} ---\n{message.body}\n---\n")


async def _smtp_send(message: EmailMessage) -> None:  # pragma: no cover - needs real SMTP
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(message.body)
    msg["Subject"] = message.subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = message.to

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, [message.to], msg.as_string())


async def send(message: EmailMessage) -> None:
    if settings.EMAIL_PROVIDER == "smtp":
        await _smtp_send(message)
    else:
        await _console_send(message)


async def send_verification_email(to: str, raw_token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    await send(EmailMessage(to=to, subject="Verify your MenuQR email", body=f"Verify here: {link}"))


async def send_password_reset_email(to: str, raw_token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    await send(EmailMessage(to=to, subject="Reset your MenuQR password", body=f"Reset here: {link}"))


async def send_invitation_email(to: str, raw_token: str, tenant_name: str) -> None:
    link = f"{settings.FRONTEND_URL}/accept-invitation?token={raw_token}"
    await send(
        EmailMessage(
            to=to,
            subject=f"You've been invited to join {tenant_name} on MenuQR",
            body=f"Accept your invitation here: {link}",
        )
    )


async def send_invitation_accepted_email(to: str, tenant_name: str) -> None:
    await send(
        EmailMessage(
            to=to, subject=f"Welcome to {tenant_name}", body=f"You have joined {tenant_name}."
        )
    )
