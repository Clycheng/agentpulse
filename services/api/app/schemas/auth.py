from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str


class WorkspaceOut(BaseModel):
    id: str
    name: str
    onboarding_completed: bool


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    workspace: WorkspaceOut


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    workspace_name: str = Field(default="我的一人公司", min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)
