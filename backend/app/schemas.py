from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    """`role` es el código de un rol de la tabla role_definitions: uno de empleado de fábrica o uno personalizado activo."""
    full_name: str = Field(min_length=3, max_length=140, pattern=r".*\S.*")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=40)
    branch: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def employee_requires_branch(self):
        if not self.branch:
            raise ValueError("La sucursal es obligatoria para empleados")
        return self


class PermisoResumen(BaseModel):
    codigo: str
    nombre: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    role: Role
    role_name: str | None = None  # nombre del rol personalizado (cuando role = PERSONALIZADO)
    permisos: list[PermisoResumen] = []  # permisos efectivos ahora mismo (los llena permisos.usuario_con_permisos)
    branch: str | None
    is_active: bool


class RoleCreate(BaseModel):
    code: str = Field(min_length=3, max_length=40, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=3, max_length=80, pattern=r".*\S.*")
    description: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def cannot_replace_system_role(self):
        if self.code in {role.value for role in Role}:
            raise ValueError("La clave pertenece a un rol protegido del sistema")
        return self


class RoleUpdate(BaseModel):
    """La clave no se puede cambiar: otras partes del sistema pueden referirse a ella."""
    name: str = Field(min_length=3, max_length=80, pattern=r".*\S.*")
    description: str | None = Field(default=None, max_length=250)


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str | None
    bin_status: int = 1
    es_sistema: bool = False
    empleados: int = 0  # usuarios que tienen este rol
    permisos: list[str] = []  # códigos de los permisos del rol


class RegisterRequest(BaseModel):
    """Registro público: crea una cuenta con rol INVITADO. El rol nunca lo elige quien se registra."""
    full_name: str = Field(min_length=3, max_length=140, pattern=r".*\S.*")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


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
