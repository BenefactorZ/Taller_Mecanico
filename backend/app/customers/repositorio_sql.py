"""Implementación SQLAlchemy de los puertos del módulo. No hace commit: lo hace el endpoint, para que Customer y Auditoría se guarden juntos."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .dominio import Auditoria, Customer, PaginaResultados, ReglaIncumplida, SolicitudPagina
from .modelos import AuditoriaModel, CustomerModel
from .normalizacion import normalizar_nombre


def _a_dominio(fila: CustomerModel) -> Customer:
    return Customer(fila.id, fila.nombre_completo, fila.telefono, fila.correo, fila.taller_id, fila.estado)


class CustomerSqlRepositorio:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _pagina(self, taller_id: int, condicion, pagina: SolicitudPagina) -> PaginaResultados:
        base = select(CustomerModel).where(CustomerModel.taller_id == taller_id, condicion)
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        filas = self._db.scalars(
            base.order_by(CustomerModel.nombre_clave, CustomerModel.id).offset((pagina.numero - 1) * pagina.tamano).limit(pagina.tamano)
        )
        return PaginaResultados(tuple(_a_dominio(f) for f in filas), total, pagina.numero, pagina.tamano)

    def buscar_por_contacto(self, taller_id: int, contacto: str, pagina: SolicitudPagina) -> PaginaResultados:
        """Un contacto es un teléfono o un correo: coincide con cualquiera de los dos medios del cliente."""
        return self._pagina(taller_id, (CustomerModel.telefono == contacto) | (CustomerModel.correo == contacto), pagina)

    def buscar_por_nombre(self, taller_id: int, nombre: str, pagina: SolicitudPagina) -> PaginaResultados:
        return self._pagina(taller_id, CustomerModel.nombre_clave.contains(nombre, autoescape=True), pagina)

    def obtener(self, taller_id: int, customer_id: int) -> Customer | None:
        fila = self._db.scalar(select(CustomerModel).where(CustomerModel.id == customer_id, CustomerModel.taller_id == taller_id))
        return _a_dominio(fila) if fila else None

    def guardar(self, customer: Customer) -> Customer:
        fila = CustomerModel(
            taller_id=customer.taller_id, nombre_completo=customer.nombre_completo,
            nombre_clave=normalizar_nombre(customer.nombre_completo), telefono=customer.telefono, correo=customer.correo,
            contacto=customer.correo or customer.telefono or "", estado=customer.estado,
        )
        self._db.add(fila)
        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            raise ReglaIncumplida("DUPLICADO", "Ya existe un cliente con ese teléfono o correo en este taller")
        return _a_dominio(fila)


class AuditoriaSqlRepositorio:
    def __init__(self, db: Session) -> None:
        self._db = db

    def registrar(self, registro: Auditoria) -> None:
        self._db.add(AuditoriaModel(
            accion=registro.accion, usuario_id=registro.usuario_id, taller_id=registro.taller_id,
            customer_id=registro.customer_id, detalle=registro.detalle[:250], fecha=registro.fecha.replace(tzinfo=None),
        ))
