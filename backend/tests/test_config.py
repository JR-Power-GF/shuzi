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


def test_validate_secret_key_rejects_default():
    """P0 fix: startup must reject the default SECRET_KEY."""
    from app.config import _DEFAULT_SECRET_KEY
    assert _DEFAULT_SECRET_KEY == "dev-secret-key-change-in-production"

    import importlib
    import app.config as config_mod

    original = os.environ.get("SECRET_KEY")
    try:
        os.environ["SECRET_KEY"] = _DEFAULT_SECRET_KEY
        importlib.reload(config_mod)
        with pytest.raises(ValueError, match="SECRET_KEY"):
            config_mod.validate_secret_key(config_mod.settings)
    finally:
        if original is None:
            os.environ.pop("SECRET_KEY", None)
        else:
            os.environ["SECRET_KEY"] = original
        importlib.reload(config_mod)


def test_validate_secret_key_accepts_custom():
    """A non-default SECRET_KEY should pass validation."""
    from app.config import validate_secret_key, _DEFAULT_SECRET_KEY
    import importlib
    import app.config as config_mod

    original = os.environ.get("SECRET_KEY")
    try:
        os.environ["SECRET_KEY"] = "a-real-production-key-that-is-long-enough"
        importlib.reload(config_mod)
        # Should not raise
        config_mod.validate_secret_key(config_mod.settings)
    finally:
        if original is None:
            os.environ.pop("SECRET_KEY", None)
        else:
            os.environ["SECRET_KEY"] = original
        importlib.reload(config_mod)
