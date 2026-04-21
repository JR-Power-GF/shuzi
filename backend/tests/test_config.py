import os
import pytest


def test_settings_loads_defaults():
    os.environ.setdefault("DATABASE_URL", "mysql+aiomysql://root:rootpassword@127.0.0.1:3306/training_platform")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-dev-only")
    from app.config import settings

    assert settings.DATABASE_URL is not None
    assert settings.SECRET_KEY is not None
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert settings.MAX_FILE_SIZE_MB > 0
    assert isinstance(settings.ALLOWED_FILE_TYPES, list)
    assert len(settings.ALLOWED_FILE_TYPES) > 0


def test_settings_has_upload_dir():
    from app.config import settings

    assert settings.UPLOAD_DIR is not None
    assert "uploads" in settings.UPLOAD_DIR
