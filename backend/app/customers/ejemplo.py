"""Ejemplo ejecutable con repositorios en memoria: `python -m app.customers.ejemplo` desde `backend/`."""
from dataclasses import replace

from .dominio import (
    Auditoria, ContextoSolicitud, Customer, DatosCliente, PaginaResultados, ReglaIncumplida, ResultadoAlta,
    SolicitudPagina, Taller, Usuario,
)
from .fachada import CustomerFacade
from .normalizacion import normalizar_nombre


class CustomerEnMemoria:
    def __init__(self) -> None:
        self.datos: dict[int, Customer] = {}

    def _pagina(self, items: list[Customer], pagina: SolicitudPagina) -> PaginaResultados:
        inicio = (pagina.numero - 1) * pagina.tamano
        return PaginaResultados(tuple(items[inicio:inicio + pagina.tamano]), len(items), pagina.numero, pagina.tamano)

    def buscar_por_contacto(self, taller_id: int, contacto: str, pagina: SolicitudPagina) -> PaginaResultados:
        return self._pagina([c for c in self.datos.values() if c.taller_id == taller_id and contacto in (c.telefono, c.correo)], pagina)

    def buscar_por_nombre(self, taller_id: int, nombre: str, pagina: SolicitudPagina) -> PaginaResultados:
        return self._pagina([c for c in self.datos.values() if c.taller_id == taller_id and nombre in normalizar_nombre(c.nombre_completo)], pagina)

    def obtener(self, taller_id: int, customer_id: int) -> Customer | None:
        customer = self.datos.get(customer_id)
        return customer if customer and customer.taller_id == taller_id else None

    def guardar(self, customer: Customer) -> Customer:
        guardado = replace(customer, id=len(self.datos) + 1)
        self.datos[guardado.id] = guardado
        return guardado


class AuditoriaEnMemoria:
    def __init__(self) -> None:
        self.registros: list[Auditoria] = []

    def registrar(self, registro: Auditoria) -> None:
        self.registros.append(registro)


def main() -> None:
    repo, auditoria = CustomerEnMemoria(), AuditoriaEnMemoria()
    facade = CustomerFacade(repo, auditoria)
    PERMISOS_RECEPCION = frozenset({"clientes.alta", "clientes.consultar"})
    contexto = ContextoSolicitud(Usuario(1, "RECEPCIONISTA", True, PERMISOS_RECEPCION), Taller(1, True))
    datos = DatosCliente("  María   López ", "55 1234 5678", "Maria.Lopez@Correo.com")

    print("1. Alta sin coincidencias, sin confirmar ->", facade.AltaCliente(contexto, datos).resultado.value)
    creado = facade.AltaCliente(contexto, datos, confirmar=True)
    print("2. Alta confirmada ->", creado.resultado.value, creado.customer)
    segundo = facade.AltaCliente(contexto, DatosCliente("Maria Lopez", "55 8765 4321", "otro@correo.com"), confirmar=True)
    print("3. Mismo nombre, confirmando ->", segundo.resultado.value, f"({len(segundo.coincidencias)} coincidencia) sin crear un segundo registro")
    pagina = facade.ConsultarCliente(contexto, "maria.lopez@correo.com")
    print("4. Consulta por contacto ->", pagina.total, "resultado;", "ficha:", facade.obtener_ficha(contexto, pagina.items[0].id).estado.value)
    print("5. Registros de auditoría ->", [r.accion for r in auditoria.registros])
    for etiqueta, ctx in (("sin sesión", ContextoSolicitud(Usuario(2, "RECEPCIONISTA", False, PERMISOS_RECEPCION), Taller(1, True))),
                          ("rol sin permiso", ContextoSolicitud(Usuario(3, "TECNICO", True, frozenset({"ordenes.consultar"})), Taller(1, True))),
                          ("taller inactivo", ContextoSolicitud(Usuario(1, "RECEPCIONISTA", True, PERMISOS_RECEPCION), Taller(1, False)))):
        try:
            facade.AltaCliente(ctx, datos)
        except ReglaIncumplida as error:
            print(f"6. Guarda ({etiqueta}) ->", error.codigo)
    assert creado.resultado is ResultadoAlta.CREADO and len(repo.datos) == 1


if __name__ == "__main__":
    main()
