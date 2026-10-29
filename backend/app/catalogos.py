"""Catálogos de apoyo: estatus (borrado lógico) y códigos postales de México."""
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base

STATUS_ACTIVO = 1
STATUS_ELIMINADO = 2
STATUS_INICIALES = (
    (STATUS_ACTIVO, "activo", "Registro activo"),
    (STATUS_ELIMINADO, "eliminado", "Registro eliminado lógicamente (borrado lógico)"),
)


class StatusModel(Base):
    """Estatus de un registro. `bin_status` de otras tablas apunta a `status.id`; nada se borra físicamente."""
    __tablename__ = "status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    valor: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    descripcion: Mapped[str] = mapped_column(String(120), nullable=False)


class CodigoPostalModel(Base):
    """Catálogo Nacional de Códigos Postales (Correos de México). Un CP pertenece a un solo municipio y estado."""
    __tablename__ = "codigos_postales"
    __table_args__ = (
        Index("ix_codigos_postales_cp", "codigo_postal"),
        Index("ix_codigos_postales_estado_municipio", "estado", "municipio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_postal: Mapped[str] = mapped_column(String(5), nullable=False)
    colonia: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo_asentamiento: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    municipio: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(String(60), nullable=False)


def sembrar_status(db: Session) -> None:
    """Inserta los estatus base si faltan (idempotente)."""
    existentes = set(db.scalars(select(StatusModel.id)))
    for id_, valor, descripcion in STATUS_INICIALES:
        if id_ not in existentes:
            db.add(StatusModel(id=id_, valor=valor, descripcion=descripcion))
    db.commit()


class PermisoModel(Base):
    """Catálogo de permisos (se siembra desde app/permisos.py)."""
    __tablename__ = "permisos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    modulo: Mapped[str] = mapped_column(String(40), nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    delegable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    en_desarrollo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RolPermisoModel(Base):
    """Permisos de un rol personalizado (los de fábrica están en el código)."""
    __tablename__ = "roles_permisos"
    __table_args__ = (UniqueConstraint("role_definition_id", "permiso_id", name="uq_roles_permisos"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_definition_id: Mapped[int] = mapped_column(ForeignKey("role_definitions.id"), nullable=False, index=True)
    permiso_id: Mapped[int] = mapped_column(ForeignKey("permisos.id"), nullable=False)
