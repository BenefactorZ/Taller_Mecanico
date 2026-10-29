"""Tabla de vehículos. Se crea con `Base.metadata.create_all` al iniciar la API (no modifica tablas existentes)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from ..catalogos import STATUS_ACTIVO
from ..database import Base


class VehiculoModel(Base):
    """Vehículo de un cliente. Hereda el taller del cliente; el VIN y la placa son únicos en todo el sistema.

    Se da de baja con borrado lógico (`bin_status`), como el resto de los registros; al registrarse queda activo.
    """
    __tablename__ = "vehiculos"
    __table_args__ = (UniqueConstraint("vin", name="uq_vehiculos_vin"), UniqueConstraint("placa", name="uq_vehiculos_placa"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(17), nullable=False)
    placa: Mapped[str] = mapped_column(String(10), nullable=False)
    marca: Mapped[str] = mapped_column(String(40), nullable=False)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(30), nullable=False)
    kilometraje: Mapped[int | None] = mapped_column(Integer, nullable=True)
    foto: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bin_status: Mapped[int] = mapped_column(ForeignKey("status.id"), nullable=False, default=STATUS_ACTIVO, server_default=text("1"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
