from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .catalogos import STATUS_ACTIVO
from .database import Base


class Role(str, Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    RECEPCIONISTA = "RECEPCIONISTA"
    ASESOR_SERVICIO = "ASESOR_SERVICIO"
    TECNICO = "TECNICO"
    CLIENTE = "CLIENTE"
    SISTEMA = "SISTEMA"
    INVITADO = "INVITADO"  # cuenta autoregistrada, sin permisos hasta que un administrador le asigne un rol
    PERSONALIZADO = "PERSONALIZADO"  # empleado con un rol personalizado (role_definition_id); sin permisos propios todavía


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(140), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SqlEnum(Role), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Sólo se usa con role = PERSONALIZADO: apunta al rol de la tabla role_definitions que eligió el administrador
    role_definition_id: Mapped[int | None] = mapped_column(ForeignKey("role_definitions.id"), nullable=True)
    role_definition: Mapped["RoleDefinition | None"] = relationship(lazy="joined")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Borrado lógico (status.id): al eliminar una cuenta también se desactiva (is_active), que es lo que revisa el acceso
    bin_status: Mapped[int] = mapped_column(ForeignKey("status.id"), nullable=False, default=STATUS_ACTIVO, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def role_name(self) -> str | None:
        """Nombre del rol personalizado, si tiene uno."""
        return self.role_definition.name if self.role_definition else None


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RoleDefinition(Base):
    __tablename__ = "role_definitions"
    __table_args__ = (UniqueConstraint("code", name="uq_role_definitions_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(250), nullable=True)
    # Borrado lógico: apunta a status.id (1 activo, 2 eliminado); el rol nunca se borra físicamente
    bin_status: Mapped[int] = mapped_column(ForeignKey("status.id"), nullable=False, default=STATUS_ACTIVO, server_default=text("1"))
    # Roles de fábrica (los del enum Role): se muestran en la administración pero no se editan ni se eliminan
    es_sistema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
