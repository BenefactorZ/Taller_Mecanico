"""Patrón Chain of Responsibility: pasos del alta encadenados, con salida temprana."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self

from .dominio import ContextoSolicitud, Customer, DatosCliente, DatosNormalizados, ReglaIncumplida, SolicitudPagina
from .estrategias import EstrategiaBusqueda
from .normalizacion import normalizar_nombre, normalizar_y_validar
from .puertos import CustomerRepositorio

# Permisos que exigen las operaciones (el administrador no tiene el de clientes: no tiene sucursal y no opera sobre un Taller concreto)
PERMISO_ALTA = "clientes.alta"
PERMISO_CONSULTA = "clientes.consultar"


@dataclass
class Solicitud:
    contexto: ContextoSolicitud


@dataclass
class SolicitudAlta(Solicitud):
    datos: DatosCliente
    confirmar: bool = False
    normalizados: DatosNormalizados | None = None
    coincidencias: tuple[Customer, ...] = ()


class Manejador(ABC):
    """Handler: ejecuta su paso y delega al siguiente; si incumple una regla, lanza ReglaIncumplida y la cadena se corta."""

    def __init__(self) -> None:
        self._siguiente: Manejador | None = None

    def enlazar(self, siguiente: "Manejador") -> "Manejador":
        self._siguiente = siguiente
        return siguiente

    def manejar(self, solicitud: Solicitud) -> None:
        self._verificar(solicitud)
        if self._siguiente:
            self._siguiente.manejar(solicitud)

    @abstractmethod
    def _verificar(self, solicitud: Solicitud) -> None: ...


class AutenticacionHandler(Manejador):
    def _verificar(self, solicitud: Solicitud) -> None:
        if not solicitud.contexto.usuario.autenticado:
            raise ReglaIncumplida("NO_AUTENTICADO", "Sesión no válida")


class AutorizacionHandler(Manejador):
    """Exige que el Usuario tenga el permiso de la operación (lo concede su rol, de fábrica o personalizado)."""

    def __init__(self, permiso: str) -> None:
        super().__init__()
        self._permiso = permiso

    def _verificar(self, solicitud: Solicitud) -> None:
        if self._permiso not in solicitud.contexto.usuario.permisos:
            raise ReglaIncumplida("NO_AUTORIZADO", "No tiene permiso para esta operación de clientes")


class TallerActivoHandler(Manejador):
    def _verificar(self, solicitud: Solicitud) -> None:
        if not solicitud.contexto.taller.activo:
            raise ReglaIncumplida("TALLER_INACTIVO", "Su sucursal no está registrada como taller activo. Pida a un administrador o recepcionista que registre el taller")


class FormatoHandler(Manejador):
    """Normaliza la captura y valida su formato (nombre completo, teléfono y correo)."""

    def _verificar(self, solicitud: Solicitud) -> None:
        assert isinstance(solicitud, SolicitudAlta)
        solicitud.normalizados = normalizar_y_validar(solicitud.datos)


class CoincidenciasHandler(Manejador):
    """Busca coincidencias por teléfono, por correo y por nombre; sólo las anota. Decidir qué hacer es de la política."""

    def __init__(self, repo: CustomerRepositorio, por_contacto: EstrategiaBusqueda, por_nombre: EstrategiaBusqueda) -> None:
        super().__init__()
        self._repo, self._por_contacto, self._por_nombre = repo, por_contacto, por_nombre

    def _verificar(self, solicitud: Solicitud) -> None:
        assert isinstance(solicitud, SolicitudAlta) and solicitud.normalizados
        taller_id, pagina = solicitud.contexto.taller.id, SolicitudPagina(1, 10)
        encontrados = {
            *self._por_contacto.buscar(self._repo, taller_id, solicitud.normalizados.telefono, pagina).items,
            *self._por_contacto.buscar(self._repo, taller_id, solicitud.normalizados.correo, pagina).items,
            *self._por_nombre.buscar(self._repo, taller_id, normalizar_nombre(solicitud.normalizados.nombre_completo), pagina).items,
        }
        solicitud.coincidencias = tuple(sorted(encontrados, key=lambda c: c.id or 0))


def encadenar(*manejadores: Manejador) -> Manejador:
    """Enlaza los manejadores en el orden recibido y devuelve el primero."""
    for actual, siguiente in zip(manejadores, manejadores[1:]):
        actual.enlazar(siguiente)
    return manejadores[0]


def construir_guardas(permiso: str) -> Manejador:
    """Autenticación → autorización (con el permiso de la operación) → taller activo."""
    return encadenar(AutenticacionHandler(), AutorizacionHandler(permiso), TallerActivoHandler())


def construir_cadena_alta(repo: CustomerRepositorio, por_contacto: EstrategiaBusqueda, por_nombre: EstrategiaBusqueda) -> Manejador:
    return encadenar(
        AutenticacionHandler(), AutorizacionHandler(PERMISO_ALTA), TallerActivoHandler(),
        FormatoHandler(), CoincidenciasHandler(repo, por_contacto, por_nombre),
    )
