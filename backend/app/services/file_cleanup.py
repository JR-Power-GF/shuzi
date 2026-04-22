import glob
import os
import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.submission_file import SubmissionFile


async def cleanup_orphan_files(db: AsyncSession) -> int:
    """Delete uploaded files older than 24h that have no SubmissionFile record."""
    upload_dir = settings.UPLOAD_DIR
    if not os.path.isdir(upload_dir):
        return 0

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    deleted = 0

    result = await db.execute(select(SubmissionFile.file_path))
    tracked_paths = set(result.scalars().all())

    for filepath in glob.glob(os.path.join(upload_dir, "*")):
        if os.path.isdir(filepath):
            continue

        if filepath in tracked_paths:
            continue

        try:
            mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                os.remove(filepath)
                deleted += 1
        except OSError:
            continue

    return deleted
