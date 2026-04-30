"""Celery tasks for email delivery.

Provides tasks for sending verification emails, password reset emails,
and general notification emails. Each task retries up to 3 times with
exponential backoff on failure; failures are logged but non-blocking.

Requirements: 1.1, 1.3, 1.4, 13.6
"""

import logging

from celery.exceptions import MaxRetriesExceededError

from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


def _send_email(to: str, subject: str, body: str) -> None:
    """Send an email using the configured provider.

    This is a thin wrapper that delegates to the configured email
    service (SendGrid or AWS SES). In development/test environments
    where no API key is set, the email is logged instead of sent.

    Raises:
        Exception: On delivery failure so the caller can retry.
    """
    if not settings.email_api_key:
        logger.info(
            "Email (no provider configured) to=%s subject=%s body=%s",
            to, subject, body[:200],
        )
        return

    provider = settings.email_provider.lower()
    if provider == "sendgrid":
        _send_via_sendgrid(to, subject, body)
    elif provider in ("ses", "aws_ses"):
        _send_via_ses(to, subject, body)
    else:
        logger.warning("Unknown email provider %r, logging email instead", provider)
        logger.info("Email to=%s subject=%s", to, subject)


def _send_via_sendgrid(to: str, subject: str, body: str) -> None:
    """Send email via SendGrid API."""
    import sendgrid  # type: ignore[import-untyped]
    from sendgrid.helpers.mail import Content, Email, Mail, To  # type: ignore[import-untyped]

    sg = sendgrid.SendGridAPIClient(api_key=settings.email_api_key)
    message = Mail(
        from_email=Email(settings.email_from),
        to_emails=To(to),
        subject=subject,
        plain_text_content=Content("text/plain", body),
    )
    response = sg.client.mail.send.post(request_body=message.get())
    logger.info("SendGrid response status=%s to=%s", response.status_code, to)


def _send_via_ses(to: str, subject: str, body: str) -> None:
    """Send email via AWS SES."""
    import boto3  # type: ignore[import-untyped]

    client = boto3.client("ses")
    client.send_email(
        Source=settings.email_from,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}},
        },
    )
    logger.info("SES email sent to=%s", to)


@celery_app.task(
    name="app.tasks.email_tasks.send_verification_email",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def send_verification_email(self, player_id: str, email: str) -> None:
    """Send an account verification email to a newly registered player.

    Args:
        player_id: UUID string of the player.
        email: The player's email address.
    """
    subject = "Verify your Color Prediction Game account"
    body = (
        f"Welcome to Color Prediction Game!\n\n"
        f"Please verify your email by clicking the link below:\n"
        f"https://colorprediction.local/verify?player_id={player_id}\n\n"
        f"If you did not create this account, please ignore this email."
    )
    try:
        _send_email(email, subject, body)
        logger.info("Verification email sent to %s (player %s)", email, player_id)
    except Exception as exc:
        logger.warning(
            "Failed to send verification email to %s (attempt %d/%d): %s",
            email, self.request.retries + 1, self.max_retries + 1, exc,
        )
        try:
            self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exhausted sending verification email to %s: %s",
                email, exc,
            )


@celery_app.task(
    name="app.tasks.email_tasks.send_password_reset_email",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def send_password_reset_email(
    self, player_id: str, email: str, reset_token: str
) -> None:
    """Send a password reset email with a time-limited token.

    Args:
        player_id: UUID string of the player.
        email: The player's email address.
        reset_token: JWT reset token (1-hour expiry).
    """
    subject = "Reset your Color Prediction Game password"
    body = (
        f"You requested a password reset.\n\n"
        f"Click the link below to reset your password:\n"
        f"https://colorprediction.local/reset-password?token={reset_token}\n\n"
        f"This link expires in 1 hour.\n"
        f"If you did not request this, please ignore this email."
    )
    try:
        _send_email(email, subject, body)
        logger.info("Password reset email sent to %s (player %s)", email, player_id)
    except Exception as exc:
        logger.warning(
            "Failed to send password reset email to %s (attempt %d/%d): %s",
            email, self.request.retries + 1, self.max_retries + 1, exc,
        )
        try:
            self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exhausted sending password reset email to %s: %s",
                email, exc,
            )


@celery_app.task(
    name="app.tasks.email_tasks.send_notification_email",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def send_notification_email(
    self, player_id: str, notification_type: str, email: str | None = None
) -> None:
    """Send a notification email to a player.

    Supported notification types:
        - "account_locked": Account locked after failed login attempts.

    Args:
        player_id: UUID string of the player.
        notification_type: The type of notification to send.
        email: Optional player email. If not provided, looked up from DB.
    """
    subjects = {
        "account_locked": "Your account has been temporarily locked",
    }
    bodies = {
        "account_locked": (
            "Your Color Prediction Game account has been temporarily locked "
            "due to multiple failed login attempts.\n\n"
            "The lock will expire in 15 minutes. If you did not attempt to "
            "log in, please reset your password immediately."
        ),
    }

    subject = subjects.get(notification_type, f"Notification: {notification_type}")
    body = bodies.get(notification_type, f"You have a new notification: {notification_type}")

    # Use provided email or fetch from DB
    if email is None:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop (e.g. eager mode in tests)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                email = pool.submit(asyncio.run, _get_player_email(player_id)).result()
        else:
            email = asyncio.run(_get_player_email(player_id))

        if email is None:
            logger.error("Cannot send notification: player %s not found", player_id)
            return

    try:
        _send_email(email, subject, body)
        logger.info(
            "Notification email (%s) sent to %s (player %s)",
            notification_type, email, player_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to send notification email to %s (attempt %d/%d): %s",
            email, self.request.retries + 1, self.max_retries + 1, exc,
        )
        try:
            self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exhausted sending notification to %s: %s",
                email, exc,
            )


async def _get_player_email(player_id: str) -> str | None:
    """Look up a player's email address from the database."""
    from uuid import UUID

    from sqlalchemy import select

    from app.models.base import async_session_factory
    from app.models.player import Player

    async with async_session_factory() as session:
        result = await session.execute(
            select(Player.email).where(Player.id == UUID(player_id))
        )
        return result.scalar_one_or_none()
