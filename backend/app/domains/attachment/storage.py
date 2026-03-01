import os
import uuid
from datetime import datetime, timezone

import aiofiles

from app.config import settings


async def save_file(tenant_id: str, filename: str, content: bytes) -> str:
    """Save a file and return the stored path relative to UPLOAD_DIR."""
    now = datetime.now(timezone.utc)
    ext = os.path.splitext(filename)[1] if "." in filename else ""
    stored_name = f"{uuid.uuid4()}{ext}"
    relative_dir = f"{tenant_id}/{now.strftime('%Y-%m')}"
    full_dir = os.path.join(settings.UPLOAD_DIR, relative_dir)
    os.makedirs(full_dir, exist_ok=True)

    full_path = os.path.join(full_dir, stored_name)
    async with aiofiles.open(full_path, "wb") as f:
        await f.write(content)

    return f"{relative_dir}/{stored_name}"


def get_full_path(stored_path: str) -> str:
    return os.path.join(settings.UPLOAD_DIR, stored_path)
