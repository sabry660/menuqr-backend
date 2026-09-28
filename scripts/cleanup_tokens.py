"""Delete expired auth tokens and expire stale invitations.

Run on a schedule (cron / Kubernetes CronJob), e.g. daily:
    python scripts/cleanup_tokens.py
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, update  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.enums import InvitationStatus  # noqa: E402
from app.models.tenant import Invitation  # noqa: E402
from app.models.user import EmailVerificationToken, PasswordResetToken, RefreshToken  # noqa: E402

RETENTION_DAYS = 7


async def main() -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    async with AsyncSessionLocal() as db:
        counts = {}
        for model in (RefreshToken, PasswordResetToken, EmailVerificationToken):
            result = await db.execute(delete(model).where(model.expires_at < cutoff))
            counts[model.__tablename__] = result.rowcount
        result = await db.execute(
            update(Invitation)
            .where(Invitation.status == InvitationStatus.PENDING, Invitation.expires_at < now)
            .values(status=InvitationStatus.EXPIRED)
        )
        counts["invitations_expired"] = result.rowcount
        await db.commit()
    print("Cleanup complete:", counts)


if __name__ == "__main__":
    asyncio.run(main())
