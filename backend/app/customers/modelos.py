"""Tablas del módulo Clientes: Taller, Customer y Auditoría. Se crean con `Base.metadata.create_all` al iniciar la API."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from ..catalogos import STATUS_ACTIVO
from ..database import Base
from .dominio import EstadoCustomer


class TallerModel(Base):
    """Taller mecánico. Los usuarios se asocian por el nombre de su sucursal. Se elimina con borrado lógico (`bin_status`)."""
    __tablename__ = "talleres"
    __table_args__ = (
        UniqueConstraint("nombre", name="uq_talleres_nombre"),
        # El RFC es único entre los talleres que lo tienen; el filtro permite filas antiguas sin RFC (NULL)
        Index("uq_talleres_rfc", "rfc", unique=True, mssql_where=text("rfc IS NOT NULL"), sqlite_where=text("rfc IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    rfc: Mapped[str | None] = mapped_column(String(13), nullable=True)
    email_contacto: Mapped[str | None] = mapped_column(String(254), nullable=True)
    calle: Mapped[str | None] = mapped_column(String(150), nullable=True)
    colonia: Mapped[str | None] = mapped_column(String(120), nullable=True)
    codigo_postal: Mapped[str | None] = mapped_column(String(5), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(60), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    foto: Mapped[str | None] = mapped_column(String(80), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bin_status: Mapped[int] = mapped_column(ForeignKey("status.id"), nullable=False, default=STATUS_ACTIVO, server_default=text("1"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CustomerModel(Base):
    __tablename__ = "customers"
    # Última defensa contra duplicados: aunque dos altas simultáneas pasen la búsqueda, la base rechaza el segundo correo o teléfono
    __table_args__ = (
        UniqueConstraint("taller_id", "contacto", name="uq_customers_taller_contacto"),
        Index("uq_customers_taller_telefono", "taller_id", "telefono", unique=True, mssql_where=text("telefono IS NOT NULL"), sqlite_where=text("telefono IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"), nullable=False, index=True)
    nombre_completo: Mapped[str] = mapped_column(String(140), nullable=False)
    nombre_clave: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    # Teléfono y correo del cliente. Un cliente anterior a la separación puede tener sólo uno; se completa al editarlo.
    telefono: Mapped[str | None] = mapped_column(String(15), nullable=True)
    correo: Mapped[str | None] = mapped_column(String(254), nullable=True)
    # Clave histórica de unicidad por taller: es el correo (o el teléfono, si aún no tiene correo). Sólo la mantiene el repositorio.
    contacto: Mapped[str] = mapped_column(String(254), nullable=False)
    estado: Mapped[EstadoCustomer] = mapped_column(SqlEnum(EstadoCustomer), nullable=False, default=EstadoCustomer.ACTIVO)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AuditoriaModel(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    accion: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    detalle: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False)
