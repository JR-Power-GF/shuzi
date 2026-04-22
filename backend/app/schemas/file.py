from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    file_token: str
    file_name: str
    file_size: int
    file_type: str
