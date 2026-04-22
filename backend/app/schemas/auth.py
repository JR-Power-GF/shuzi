from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserBrief(BaseModel):
    id: int
    username: str
    real_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool
    user: UserBrief
