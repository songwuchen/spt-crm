"""Auto-create Activity records for key business events."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.domains.activity.models import Activity


async def record_activity(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str,
                           activity_type: str, subject: str, content: str | None,
                           user_id: str, user_name: str):
    """Create an auto-generated activity record."""
    activity = Activity(
        id=generate_uuid(), tenant_id=tenant_id,
        biz_type=biz_type, biz_id=biz_id,
        activity_type=activity_type,
        subject=subject, content=content,
        created_by_id=user_id, created_by_name=user_name,
    )
    db.add(activity)
    await db.commit()
