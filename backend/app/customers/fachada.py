"""Patrón Facade: dos operaciones de dominio que ocultan cadena, estrategias, fábrica, persistencia y auditoría."""
from .cadena import PERMISO_ALTA, PERMISO_CONSULTA, Manejador, SolicitudAlta, Solicitud, construir_cadena_alta, construir_guardas
from .dominio import (
    Auditoria, ContextoSolicitud, Customer, DatosCliente, PaginaResultados, ReglaIncumplida,
    RespuestaAlta, ResultadoAlta, SolicitudPagina,
)
from .estrategias import (
    AlertarSinAutoCrear, BusquedaPorContacto, BusquedaPorNombre, DecisionAlta, PoliticaDuplicados,
    elegir_estrategia_consulta,
)
from .fabrica import CustomerActivoCreator, CustomerCreator
from .normalizacion import normalizar_criterio
from .puertos import AuditoriaRepositorio, CustomerRepositorio


class CustomerFacade:
    def __init__(
        self,
        repo: CustomerRepositorio,
        auditoria: AuditoriaRepositorio,
        politica: PoliticaDuplicados | None = None,
        creator: CustomerCreator | None = None,
    ) -> None:
        self._repo, self._auditoria = repo, auditoria
        self._politica = politica or AlertarSinAutoCrear()
        self._creator = creator or CustomerActivoCreator()
        self._guardas_alta: Manejador = construir_guardas(PERMISO_ALTA)
        self._guardas_consulta: Manejador = construir_guardas(PERMISO_CONSULTA)
        self._cadena_alta: Manejador = construir_cadena_alta(repo, BusquedaPorContacto(), BusquedaPorNombre())

    def abrir_alta(self, contexto: ContextoSolicitud) -> None:
        """Abrir alta: sólo aplica las guardas, antes de mostrar el formulario."""
        self._guardas_alta.manejar(Solicitud(contexto))

    def alta_cliente(self, contexto: ContextoSolicitud, datos: DatosCliente, confirmar: bool = False) -> RespuestaAlta:
        solicitud = SolicitudAlta(contexto, datos, confirmar)
        self._cadena_alta.manejar(solicitud)  # guardas, normalización, formato y coincidencias
        decision = self._politica.decidir(solicitud.coincidencias, confirmar)
        if decision is DecisionAlta.ALERTAR_Y_NO_CREAR:
            return RespuestaAlta(ResultadoAlta.COINCIDENCIAS, coincidencias=solicitud.coincidencias)
        if decision is DecisionAlta.PEDIR_CONFIRMACION:
            return RespuestaAlta(ResultadoAlta.PENDIENTE_CONFIRMACION)
        assert solicitud.normalizados
        customer = self._repo.guardar(self._creator.crear(solicitud.normalizados, contexto.taller))
        self._auditoria.registrar(Auditoria.de("ALTA_CUSTOMER", contexto, customer, "Alta confirmada sin coincidencias"))
        return RespuestaAlta(ResultadoAlta.CREADO, customer)

    def consultar_cliente(self, contexto: ContextoSolicitud, criterio: str, pagina: SolicitudPagina | None = None) -> PaginaResultados:
        self._guardas_consulta.manejar(Solicitud(contexto))
        normalizado = normalizar_criterio(criterio)
        if not normalizado:
            raise ReglaIncumplida("FORMATO_INVALIDO", "Ingrese un criterio de búsqueda")
        estrategia = elegir_estrategia_consulta(normalizado)
        return estrategia.buscar(self._repo, contexto.taller.id, normalizado, pagina or SolicitudPagina())

    def obtener_ficha(self, contexto: ContextoSolicitud, customer_id: int) -> Customer:
        self._guardas_consulta.manejar(Solicitud(contexto))
        customer = self._repo.obtener(contexto.taller.id, customer_id)
        if not customer:
            raise ReglaIncumplida("NO_ENCONTRADO", "El cliente no existe en este taller")
        return customer

    # Nombres de las operaciones tal como aparecen en el diseño
    AltaCliente = alta_cliente
    ConsultarCliente = consultar_cliente
