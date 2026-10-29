"""Administración de clientes: listar, modificar con trazabilidad, suspender y reactivar.

- **Quién modifica:** el recepcionista (sólo los clientes de su taller) y el administrador (los de todos los talleres), con el permiso
  `clientes.administrar`.
- **Quién suspende:** sólo el administrador (`clientes.suspender`). Suspender no borra al cliente: cambia su estado a INACTIVO, y un cliente
  suspendido no se modifica ni se le registran vehículos hasta que se reactive.
- **Taller:** el taller asignado al cliente nunca cambia; una solicitud que intente cambiarlo se rechaza.
- **Trazabilidad:** cada modificación, suspensión y reactivación deja una fila en `auditoria` (quién, cuándo y qué cambió), consultable en el historial.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..catalogos import STATUS_ACTIVO
from ..database import get_db
from ..models import Role, User
from ..permisos import requiere
from ..vehiculos.modelos import VehiculoModel
from .api import resolver_taller
from .dominio import DatosCliente, EstadoCustomer, ReglaIncumplida
from .modelos import AuditoriaModel, CustomerModel, TallerModel
from .normalizacion import normalizar_nombre, normalizar_telefono, normalizar_y_validar

router = APIRouter(prefix="/api/administracion/clientes", tags=["clientes-administracion"])
administrar = requiere("clientes.administrar")
suspender = requiere("clientes.suspender")


class ClienteAdminOut(BaseModel):
    id: int
    nombre_completo: str
    telefono: str | None
    correo: str | None
    datos_incompletos: bool  # cliente anterior a la separación de teléfono y correo: falta uno de los dos
    estado: EstadoCustomer
    taller_id: int
    taller: str
    vehiculos: int
    created_at: datetime


class PaginaClientesAdmin(BaseModel):
    items: list[ClienteAdminOut]
    total: int
    pagina: int
    tamano: int


class ClienteEdicionIn(BaseModel):
    """Los datos que se pueden modificar. `taller_id` existe sólo para rechazar explícitamente un intento de cambiarlo."""
    nombre_completo: str = Field(max_length=300)
    telefono: str = Field(max_length=60)
    correo: str = Field(max_length=300)
    taller_id: int | None = None
    confirmar: bool = False  # acepta guardar aunque otro cliente del taller tenga el mismo nombre


class MotivoIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=200, pattern=r".*\S.*")


class MovimientoOut(BaseModel):
    id: int
    accion: str
    detalle: str
    usuario: str
    fecha: datetime


def alcance_de(db: Session, user: User) -> int | None:
    """Taller al que está limitada la persona. `None` = todos (administrador, que no pertenece a un taller)."""
    if user.role is Role.ADMINISTRADOR:
        return None
    taller, _ = resolver_taller(db, user)
    if taller.id == 0 or not taller.activo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Su sucursal no corresponde a un taller registrado y activo; pida al administrador que la corrija")
    return taller.id


def _salida(db: Session, filas: list[CustomerModel]) -> list[ClienteAdminOut]:
    if not filas:
        return []
    ids = [f.id for f in filas]
    talleres = dict(db.execute(select(TallerModel.id, TallerModel.nombre).where(TallerModel.id.in_({f.taller_id for f in filas}))).all())
    vehiculos = dict(db.execute(select(VehiculoModel.customer_id, func.count()).where(VehiculoModel.customer_id.in_(ids), VehiculoModel.bin_status == STATUS_ACTIVO).group_by(VehiculoModel.customer_id)).all())
    return [ClienteAdminOut(id=f.id, nombre_completo=f.nombre_completo, telefono=f.telefono, correo=f.correo, datos_incompletos=not (f.telefono and f.correo), estado=f.estado, taller_id=f.taller_id,
                            taller=talleres.get(f.taller_id, ""), vehiculos=vehiculos.get(f.id, 0), created_at=f.created_at) for f in filas]


def cliente_en_alcance(db: Session, user: User, customer_id: int) -> CustomerModel:
    """El cliente, si existe y la persona puede administrarlo. Fuera de su alcance responde 404 (no revela que existe)."""
    fila = db.get(CustomerModel, customer_id)
    taller_id = alcance_de(db, user)
    if fila is None or (taller_id is not None and fila.taller_id != taller_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El cliente no existe")
    return fila


def _auditar(db: Session, accion: str, usuario: User, cliente: CustomerModel, detalle: str) -> None:
    db.add(AuditoriaModel(accion=accion, usuario_id=usuario.id, taller_id=cliente.taller_id, customer_id=cliente.id, detalle=detalle[:250], fecha=datetime.utcnow()))


def _corto(texto: str, largo: int = 55) -> str:
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


@router.get("", response_model=PaginaClientesAdmin)
def listar_clientes(
    buscar: str = Query("", max_length=140), estado: str = Query("", pattern=r"^(ACTIVO|INACTIVO)?$"), taller_id: int | None = Query(None, ge=1),
    pagina: int = Query(1, ge=1), tamano: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db), usuario: User = Depends(administrar),
):
    """Clientes con búsqueda (nombre, teléfono o correo), filtro por estado y paginación. El administrador puede filtrar por taller."""
    limite = alcance_de(db, usuario)
    consulta = select(CustomerModel)
    if limite is not None:
        consulta = consulta.where(CustomerModel.taller_id == limite)
    elif taller_id:
        consulta = consulta.where(CustomerModel.taller_id == taller_id)
    if estado:
        consulta = consulta.where(CustomerModel.estado == EstadoCustomer(estado))
    if buscar.strip():
        texto = buscar.strip()
        condiciones = [CustomerModel.nombre_clave.contains(normalizar_nombre(texto), autoescape=True), func.lower(CustomerModel.correo).contains(texto.lower(), autoescape=True)]
        if normalizar_telefono(texto):
            condiciones.append(CustomerModel.telefono.contains(normalizar_telefono(texto), autoescape=True))
        consulta = consulta.where(or_(*condiciones))
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = list(db.scalars(consulta.order_by(CustomerModel.nombre_clave, CustomerModel.id).offset((pagina - 1) * tamano).limit(tamano)))
    return PaginaClientesAdmin(items=_salida(db, filas), total=total, pagina=pagina, tamano=tamano)


@router.get("/{customer_id}", response_model=ClienteAdminOut)
def ver_cliente(customer_id: int, db: Session = Depends(get_db), usuario: User = Depends(administrar)):
    return _salida(db, [cliente_en_alcance(db, usuario, customer_id)])[0]


@router.put("/{customer_id}", response_model=ClienteAdminOut)
def modificar_cliente(customer_id: int, payload: ClienteEdicionIn, db: Session = Depends(get_db), usuario: User = Depends(administrar)):
    """Modifica nombre, teléfono y correo con las mismas reglas de formato del alta. El taller asignado no se puede cambiar."""
    cliente = cliente_en_alcance(db, usuario, customer_id)
    if payload.taller_id is not None and payload.taller_id != cliente.taller_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "El taller asignado al cliente no se puede cambiar")
    if cliente.estado is EstadoCustomer.INACTIVO:
        raise ReglaIncumplida("CLIENTE_SUSPENDIDO", "El cliente está suspendido; un administrador debe reactivarlo antes de modificarlo")
    datos = normalizar_y_validar(DatosCliente(payload.nombre_completo, payload.telefono, payload.correo))
    cambios = []
    if datos.nombre_completo != cliente.nombre_completo:
        cambios.append(f"nombre: de «{_corto(cliente.nombre_completo)}» a «{_corto(datos.nombre_completo)}»")
    if datos.telefono != cliente.telefono:
        cambios.append(f"teléfono: de «{_corto(cliente.telefono or 'sin dato')}» a «{datos.telefono}»")
    if datos.correo != cliente.correo:
        cambios.append(f"correo: de «{_corto(cliente.correo or 'sin dato')}» a «{_corto(datos.correo)}»")
    if cambios:
        for campo, valor, etiqueta in ((CustomerModel.telefono, datos.telefono, "teléfono"), (CustomerModel.correo, datos.correo, "correo")):
            otro = db.scalar(select(CustomerModel).where(CustomerModel.taller_id == cliente.taller_id, campo == valor, CustomerModel.id != cliente.id))
            if otro:
                raise ReglaIncumplida("DUPLICADO", f"Ya existe otro cliente con ese {etiqueta} en este taller ({otro.nombre_completo}, ID {otro.id})")
        clave = normalizar_nombre(datos.nombre_completo)
        mismo_nombre = db.scalar(select(CustomerModel).where(CustomerModel.taller_id == cliente.taller_id, CustomerModel.nombre_clave == clave, CustomerModel.id != cliente.id))
        if mismo_nombre and not payload.confirmar:
            raise ReglaIncumplida("COINCIDENCIA", f"Ya existe otro cliente con ese nombre en este taller (ID {mismo_nombre.id}, {mismo_nombre.correo or mismo_nombre.telefono}). Confirme si se trata de otra persona")
        cliente.nombre_completo, cliente.nombre_clave = datos.nombre_completo, clave
        cliente.telefono, cliente.correo, cliente.contacto = datos.telefono, datos.correo, datos.correo  # `contacto` conserva la clave de unicidad por taller
        _auditar(db, "ACTUALIZAR_CUSTOMER", usuario, cliente, "; ".join(cambios))
        db.commit()
        db.refresh(cliente)
    return _salida(db, [cliente])[0]


@router.post("/{customer_id}/suspender", response_model=ClienteAdminOut)
def suspender_cliente(customer_id: int, payload: MotivoIn, db: Session = Depends(get_db), usuario: User = Depends(suspender)):
    cliente = cliente_en_alcance(db, usuario, customer_id)
    if cliente.estado is EstadoCustomer.INACTIVO:
        raise ReglaIncumplida("ESTADO_INVALIDO", "El cliente ya está suspendido")
    cliente.estado = EstadoCustomer.INACTIVO
    _auditar(db, "SUSPENDER_CUSTOMER", usuario, cliente, f"Motivo: {payload.motivo.strip()}")
    db.commit()
    db.refresh(cliente)
    return _salida(db, [cliente])[0]


@router.post("/{customer_id}/reactivar", response_model=ClienteAdminOut)
def reactivar_cliente(customer_id: int, db: Session = Depends(get_db), usuario: User = Depends(suspender)):
    cliente = cliente_en_alcance(db, usuario, customer_id)
    if cliente.estado is EstadoCustomer.ACTIVO:
        raise ReglaIncumplida("ESTADO_INVALIDO", "El cliente no está suspendido")
    cliente.estado = EstadoCustomer.ACTIVO
    _auditar(db, "REACTIVAR_CUSTOMER", usuario, cliente, "Cliente reactivado")
    db.commit()
    db.refresh(cliente)
    return _salida(db, [cliente])[0]


@router.get("/{customer_id}/historial", response_model=list[MovimientoOut])
def historial_cliente(customer_id: int, db: Session = Depends(get_db), usuario: User = Depends(administrar)):
    """Trazabilidad del cliente: alta, modificaciones, suspensiones y vehículos relacionados, del más reciente al más antiguo."""
    cliente = cliente_en_alcance(db, usuario, customer_id)
    filas = db.execute(
        select(AuditoriaModel, User.full_name).join(User, User.id == AuditoriaModel.usuario_id)
        .where(AuditoriaModel.customer_id == cliente.id).order_by(AuditoriaModel.fecha.desc(), AuditoriaModel.id.desc())
    ).all()
    return [MovimientoOut(id=a.id, accion=a.accion, detalle=a.detalle, usuario=nombre, fecha=a.fecha) for a, nombre in filas]
