"""Patrón Strategy: variantes intercambiables de búsqueda paginada y de decisión ante coincidencias."""
from abc import ABC, abstractmethod
from enum import Enum

from .dominio import Customer, PaginaResultados, SolicitudPagina
from .normalizacion import es_contacto
from .puertos import CustomerRepositorio


class EstrategiaBusqueda(ABC):
    """Strategy 1: cómo se buscan y paginan los Customer de un Taller."""

    @abstractmethod
    def buscar(self, repo: CustomerRepositorio, taller_id: int, criterio: str, pagina: SolicitudPagina) -> PaginaResultados: ...


class BusquedaPorContacto(EstrategiaBusqueda):
    def buscar(self, repo: CustomerRepositorio, taller_id: int, criterio: str, pagina: SolicitudPagina) -> PaginaResultados:
        return repo.buscar_por_contacto(taller_id, criterio, pagina)


class BusquedaPorNombre(EstrategiaBusqueda):
    def buscar(self, repo: CustomerRepositorio, taller_id: int, criterio: str, pagina: SolicitudPagina) -> PaginaResultados:
        return repo.buscar_por_nombre(taller_id, criterio, pagina)


def elegir_estrategia_consulta(criterio: str) -> EstrategiaBusqueda:
    """El contexto elige la variante según la forma del criterio, sin condicionales en la Facade."""
    return BusquedaPorContacto() if es_contacto(criterio) else BusquedaPorNombre()


class DecisionAlta(str, Enum):
    ALERTAR_Y_NO_CREAR = "ALERTAR_Y_NO_CREAR"
    PEDIR_CONFIRMACION = "PEDIR_CONFIRMACION"
    CREAR = "CREAR"


class PoliticaDuplicados(ABC):
    """Strategy 2: qué hacer con el resultado de buscar coincidencias."""

    @abstractmethod
    def decidir(self, coincidencias: tuple[Customer, ...], confirmado: bool) -> DecisionAlta: ...


class AlertarSinAutoCrear(PoliticaDuplicados):
    """Regla del negocio: una coincidencia alerta y jamás crea un segundo registro."""

    def decidir(self, coincidencias: tuple[Customer, ...], confirmado: bool) -> DecisionAlta:
        if coincidencias:
            return DecisionAlta.ALERTAR_Y_NO_CREAR
        return DecisionAlta.CREAR if confirmado else DecisionAlta.PEDIR_CONFIRMACION
