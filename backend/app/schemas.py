from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=140, pattern=r".*\S.*")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Role
    branch: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def employee_requires_branch(self):
        employee_roles = (Role.RECEPCIONISTA, Role.ASESOR_SERVICIO, Role.TECNICO)
        if self.role not in employee_roles:
            raise ValueError("Sólo se pueden dar de alta roles de empleado")
        if not self.branch:
            raise ValueError("La sucursal es obligatoria para empleados")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    role: Role
    branch: str | None
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RecoveryRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class ResetPasswordRequest(VerifyCodeRequest):
    new_password: str = Field(min_length=12, max_length=128)
