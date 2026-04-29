from pydantic_settings import BaseSettings
from typing import List

_DEFAULT_SECRET_KEY = "dev-secret-key-change-in-production"


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:rootpassword@127.0.0.1:3306/training_platform"
    SYNC_DATABASE_URL: str = "mysql+pymysql://root:rootpassword@127.0.0.1:3306/training_platform"
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    UPLOAD_DIR: str = "/uploads"
    UPLOAD_TMP_DIR: str = "/uploads/tmp"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_FILE_TYPES: List[str] = [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".zip", ".rar",
        ".jpg", ".jpeg", ".png", ".gif",
        ".mp4", ".avi", ".mov",
        ".txt", ".csv",
    ]
    LOCKOUT_THRESHOLD: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    TOTAL_SUBMISSION_SIZE_LIMIT_MB: int = 100
    AI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    AI_BASE_URL: str = ""
    XR_ENABLED: bool = False
    XR_PROVIDER: str = "null"
    XR_CALLBACK_SECRET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def validate_secret_key(s: Settings) -> None:
    if s.SECRET_KEY == _DEFAULT_SECRET_KEY:
        raise ValueError(
            "SECRET_KEY is set to the default value. "
            "Set the SECRET_KEY environment variable to a strong random string."
        )


def validate_xr_config(s: Settings) -> None:
    if s.XR_ENABLED and not s.XR_CALLBACK_SECRET:
        raise ValueError(
            "XR_CALLBACK_SECRET must be set when XR_ENABLED is True. "
            "Set the XR_CALLBACK_SECRET environment variable."
        )
