from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:rootpassword@127.0.0.1:3306/training_platform"
    SYNC_DATABASE_URL: str = "mysql+pymysql://root:rootpassword@127.0.0.1:3306/training_platform"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
