from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TaskStatus = Literal["new", "in-progress", "blocked", "completed", "not-started"]


class RoleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str | None = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = None


class RoleRead(RoleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    is_active: bool = True


class UserCreate(UserBase):
    role_ids: list[int] = Field(..., min_length=1, max_length=1)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    is_active: bool | None = None
    role_ids: list[int] | None = Field(default=None, min_length=1, max_length=1)


class UserRoleAssignment(BaseModel):
    role_ids: list[int] = Field(..., min_length=1, max_length=1)


class UserRead(UserBase):
    id: int
    avatar_url: str | None = None
    roles: list[RoleRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class GoogleLoginRequest(BaseModel):
    token: str = Field(..., min_length=20)


class AuthTokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    owner_id: int | None = None

    @field_validator("end_date")
    @classmethod
    def end_date_cannot_be_before_start_date(cls, end_date: date | None, info):
        start_date = info.data.get("start_date")
        if start_date and end_date and end_date < start_date:
            raise ValueError("end_date cannot be before start_date")
        return end_date


class ProjectCreate(ProjectBase):
    description: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    owner_id: int


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    owner_id: int | None = None

    @field_validator("end_date")
    @classmethod
    def end_date_cannot_be_before_start_date(cls, end_date: date | None, info):
        start_date = info.data.get("start_date")
        if start_date and end_date and end_date < start_date:
            raise ValueError("end_date cannot be before start_date")
        return end_date


class ProjectRead(ProjectBase):
    id: int
    owner: UserRead | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    description: str = Field(..., min_length=2)
    due_date: date | None = None
    status: TaskStatus = "not-started"
    owner_id: int | None = None
    project_id: int


class TaskCreate(TaskBase):
    due_date: date


class TaskUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=2)
    due_date: date | None = None
    status: TaskStatus | None = None
    owner_id: int | None = None
    project_id: int | None = None


class TaskAssign(BaseModel):
    owner_id: int | None = None


class TaskRead(TaskBase):
    id: int
    owner: UserRead | None = None
    project: ProjectRead | None = None

    model_config = ConfigDict(from_attributes=True)
