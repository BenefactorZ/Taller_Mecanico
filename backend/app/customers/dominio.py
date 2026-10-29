"""Modelo mínimo del dominio Customer.

Sólo existen las entidades Customer, Taller, Usuario y Auditoría. Son dataclasses
inmutables, sin dependencias de base de datos, para poder probar cada patrón por separado.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class EstadoCustomer(str, Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


@dataclass(frozen=True)
class Taller:
    id: int
    activo: bool


@dataclass(frozen=True)
class Usuario:
    id: int
    rol: str
    autenticado: bool
    permisos: frozenset[str] = frozenset()  # permisos efectivos (de su rol de fábrica o de su rol personalizado)


@dataclass(frozen=True)
class ContextoSolicitud:
    """Quién pide la operación y en qué Taller; lo exigen las guardas de ambos flujos."""
    usuario: Usuario
    taller: Taller


@dataclass(frozen=True)
class DatosCliente:
    """Captura sin procesar: nombre completo, teléfono y correo (el ID lo asigna el sistema al guardar)."""
    nombre_completo: str
    telefono: str
    correo: str


@dataclass(frozen=True)
class DatosNormalizados:
    nombre_completo: str
    telefono: str
    correo: str


@dataclass(frozen=True)
class Customer:
    """Cliente: ID, nombre, teléfono y correo. Los clientes anteriores a la separación pueden carecer de uno de los dos medios."""
    id: int | None
    nombre_completo: str
    telefono: str | None
    correo: str | None
    taller_id: int
    estado: EstadoCustomer


@dataclass(frozen=True)
class Auditoria:
    accion: str
    usuario_id: int
    taller_id: int
    customer_id: int | None
    detalle: str
    fecha: datetime

    @staticmethod
    def de(accion: str, contexto: ContextoSolicitud, customer: Customer, detalle: str = "") -> "Auditoria":
        return Auditoria(accion, contexto.usuario.id, contexto.taller.id, customer.id, detalle, datetime.now(timezone.utc))


class ReglaIncumplida(Exception):
    """Corta un flujo con un motivo explícito; la capa HTTP la traduce (401, 403, 409 o 422)."""

    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


@dataclass(frozen=True)
class SolicitudPagina:
    numero: int = 1
    tamano: int = 20

    def __post_init__(self) -> None:
        if self.numero < 1 or not 1 <= self.tamano <= 50:
            raise ReglaIncumplida("PAGINA_INVALIDA", "La página debe ser mayor a 0 y el tamaño de 1 a 50")


@dataclass(frozen=True)
class PaginaResultados:
    items: tuple[Customer, ...]
    total: int
    numero: int
    tamano: int

    @property
    def hay_mas(self) -> bool:
        return self.numero * self.tamano < self.total


class ResultadoAlta(str, Enum):
    COINCIDENCIAS = "COINCIDENCIAS"
    PENDIENTE_CONFIRMACION = "PENDIENTE_CONFIRMACION"
    CREADO = "CREADO"


@dataclass(frozen=True)
class RespuestaAlta:
    resultado: ResultadoAlta
    customer: Customer | None = None
    coincidencias: tuple[Customer, ...] = ()
