import os
import datetime
import pytest

from app.services.file_cleanup import cleanup_orphan_files


@pytest.mark.asyncio(loop_scope="session")
async def test_cleanup_orphan_files(db_session, upload_dir):
    # Create an orphan file (no submission_files record) with old mtime
    orphan_path = os.path.join(upload_dir, "orphan_test.txt")
    with open(orphan_path, "w") as f:
        f.write("orphan")

    # Set mtime to >24h ago so it's eligible for cleanup
    old_time = (datetime.datetime.utcnow() - datetime.timedelta(hours=25)).timestamp()
    os.utime(orphan_path, (old_time, old_time))

    deleted = await cleanup_orphan_files(db_session)
    assert deleted >= 1
    assert not os.path.exists(orphan_path)


@pytest.mark.asyncio(loop_scope="session")
async def test_cleanup_preserves_recent_files(db_session, upload_dir):
    recent_path = os.path.join(upload_dir, "recent_test.txt")
    with open(recent_path, "w") as f:
        f.write("recent")

    deleted = await cleanup_orphan_files(db_session)
    assert deleted == 0
    assert os.path.exists(recent_path)
