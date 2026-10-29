"""Puertos que la capa de persistencia debe implementar (SQLAlchemy en el sistema real)."""
from typing import Protocol

from .dominio import Auditoria, Customer, PaginaResultados, SolicitudPagina


class CustomerRepositorio(Protocol):
    def buscar_por_contacto(self, taller_id: int, contacto: str, pagina: SolicitudPagina) -> PaginaResultados: ...

    # `nombre` llega como clave de comparación (sin acentos ni mayúsculas): normalizar_nombre()
    def buscar_por_nombre(self, taller_id: int, nombre: str, pagina: SolicitudPagina) -> PaginaResultados: ...

    def obtener(self, taller_id: int, customer_id: int) -> Customer | None: ...

    def guardar(self, customer: Customer) -> Customer: ...


class AuditoriaRepositorio(Protocol):
    def registrar(self, registro: Auditoria) -> None: ...
