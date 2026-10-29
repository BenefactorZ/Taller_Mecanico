"""Permisos: catálogo de capacidades del sistema, permisos de cada rol y verificación en cada petición.

- El **catálogo** (`PERMISOS`) lo define el código, porque cada permiso corresponde a algo que la API realmente protege. Se siembra en la
  tabla `permisos` al arrancar.
- Los **roles de fábrica** (enum `Role`) tienen permisos fijos en `PERMISOS_SISTEMA`; reproducen exactamente las reglas que la API ya aplicaba.
- Los **roles personalizados** reciben sus permisos desde la base (`roles_permisos`), que edita el administrador. Sólo se pueden delegar los
  permisos marcados `delegable`: los de administración (alta de empleados, administración de roles y permisos) quedan reservados al
  administrador, porque delegarlos permitiría a un rol personalizado concederse más poder.
- Los permisos se leen de la base **en cada petición**: un cambio surte efecto de inmediato, sin volver a iniciar sesión.
"""
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .catalogos import STATUS_ACTIVO, STATUS_ELIMINADO, PermisoModel, RolPermisoModel
from .database import get_db
from .models import Role, RoleDefinition, User
from .schemas import PermisoResumen, UserResponse
from .security import current_user


@dataclass(frozen=True)
class Permiso:
    codigo: str
    modulo: str
    nombre: str
    descripcion: str
    delegable: bool = True
    en_desarrollo: bool = False  # el endpoint existe y se protege, pero el módulo todavía no tiene funcionalidad


PERMISOS: tuple[Permiso, ...] = (
    Permiso("empleados.alta", "Administración", "Dar de alta empleados", "Registrar empleados y asignarles un rol.", delegable=False),
    Permiso("empleados.administrar", "Administración", "Administrar empleados", "Consultar, editar, asignar rol y eliminar empleados y cuentas invitadas.", delegable=False),
    Permiso("roles.administrar", "Administración", "Administrar roles y permisos", "Crear, editar, eliminar roles y definir sus permisos.", delegable=False),
    Permiso("talleres.consultar", "Talleres", "Consultar talleres", "Ver la lista de talleres registrados y sus fotos."),
    Permiso("talleres.alta", "Talleres", "Dar de alta talleres", "Registrar talleres y usar el catálogo de códigos postales.", delegable=False),
    Permiso("talleres.administrar", "Talleres", "Administrar talleres", "Editar los datos de un taller, cambiar su foto, eliminarlo (borrado lógico) y restaurarlo.", delegable=False),
    Permiso("clientes.consultar", "Clientes", "Consultar clientes", "Buscar clientes y ver su ficha."),
    Permiso("clientes.alta", "Clientes", "Dar de alta clientes", "Registrar clientes nuevos (con alerta de duplicados)."),
    Permiso("clientes.administrar", "Clientes", "Administrar clientes", "Consultar la administración de clientes y modificar sus datos con trazabilidad (el taller asignado no cambia).", delegable=False),
    Permiso("clientes.suspender", "Clientes", "Suspender clientes", "Suspender y reactivar clientes.", delegable=False),
    Permiso("vehiculos.registrar", "Vehículos", "Registrar vehículos", "Registrar un vehículo y asociarlo a un cliente.", delegable=False),
    Permiso("vehiculos.consultar", "Vehículos", "Consultar vehículos", "Ver los vehículos registrados y su foto.", delegable=False),
    Permiso("recepciones.registrar", "Recepción de vehículos", "Registrar recepciones", "Registrar la entrada de un vehículo al taller.", en_desarrollo=True),
    Permiso("ordenes.consultar", "Órdenes de trabajo", "Consultar órdenes de trabajo", "Ver las órdenes de trabajo.", en_desarrollo=True),
    Permiso("ordenes.corregir", "Órdenes de trabajo", "Corregir órdenes de trabajo", "Corregir la información de una orden.", en_desarrollo=True),
    Permiso("diagnosticos.registrar", "Diagnósticos", "Registrar diagnósticos", "Registrar diagnósticos y reparaciones de una orden.", en_desarrollo=True),
    Permiso("notificaciones.consultar", "Notificaciones", "Consultar notificaciones", "Ver las notificaciones del sistema o del encargo.", en_desarrollo=True),
)
POR_CODIGO = {p.codigo: p for p in PERMISOS}
DELEGABLES = frozenset(p.codigo for p in PERMISOS if p.delegable)

# Permisos fijos de los roles de fábrica. Reproducen las reglas que ya aplicaba la API (el administrador no gestiona clientes: no tiene sucursal).
PERMISOS_SISTEMA: dict[Role, frozenset[str]] = {
    # El administrador no tiene sucursal: no consulta clientes de un taller, pero los administra (todos los talleres) y da de alta eligiendo el taller
    Role.ADMINISTRADOR: frozenset(p.codigo for p in PERMISOS if p.codigo != "clientes.consultar"),
    Role.RECEPCIONISTA: frozenset({"clientes.consultar", "clientes.alta", "clientes.administrar", "vehiculos.registrar", "vehiculos.consultar",
                                   "talleres.consultar", "ordenes.consultar", "recepciones.registrar"}),
    Role.ASESOR_SERVICIO: frozenset({"clientes.consultar", "clientes.alta", "ordenes.consultar", "ordenes.corregir"}),
    Role.TECNICO: frozenset({"ordenes.consultar", "diagnosticos.registrar"}),
    Role.CLIENTE: frozenset({"notificaciones.consultar"}),
    Role.SISTEMA: frozenset(),
    Role.INVITADO: frozenset(),
    Role.PERSONALIZADO: frozenset(),
}


def sembrar_permisos(db: Session) -> None:
    """Deja el catálogo en la tabla (idempotente). Actualiza textos de los que ya existen; nunca borra."""
    existentes = {p.codigo: p for p in db.scalars(select(PermisoModel))}
    for permiso in PERMISOS:
        fila = existentes.get(permiso.codigo)
        datos = dict(modulo=permiso.modulo, nombre=permiso.nombre, descripcion=permiso.descripcion, delegable=permiso.delegable, en_desarrollo=permiso.en_desarrollo)
        if fila is None:
            db.add(PermisoModel(codigo=permiso.codigo, **datos))
        else:
            for campo, valor in datos.items():
                setattr(fila, campo, valor)
    db.flush()
    # Si un permiso dejó de ser delegable, se retiran las concesiones que ya existían (aunque no se concedían, no deben quedar en la base)
    reservados = select(PermisoModel.id).where(PermisoModel.delegable == False)  # noqa: E712
    db.execute(delete(RolPermisoModel).where(RolPermisoModel.permiso_id.in_(reservados)))
    db.commit()


def permisos_de_rol_personalizado(db: Session, rol_id: int) -> frozenset[str]:
    codigos = db.scalars(select(PermisoModel.codigo).join(RolPermisoModel, RolPermisoModel.permiso_id == PermisoModel.id).where(RolPermisoModel.role_definition_id == rol_id))
    return frozenset(c for c in codigos if c in DELEGABLES)  # aunque la base tuviera otro, jamás se concede uno no delegable


def permisos_de(user: User, db: Session) -> frozenset[str]:
    """Permisos efectivos del usuario ahora mismo. Un rol personalizado eliminado no concede nada hasta que se restaure."""
    if user.role is Role.PERSONALIZADO:
        rol = user.role_definition
        if rol is None or rol.bin_status != STATUS_ACTIVO:
            return frozenset()
        return permisos_de_rol_personalizado(db, rol.id)
    return PERMISOS_SISTEMA.get(user.role, frozenset())


def requiere(codigo: str):
    """Dependencia de FastAPI: deja pasar sólo a quien tenga el permiso (403 en caso contrario)."""
    assert codigo in POR_CODIGO, f"permiso desconocido: {codigo}"

    def verificar(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        if codigo not in permisos_de(user, db):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permiso para esta operación")
        return user
    return verificar


def usuario_con_permisos(user: User, db: Session) -> UserResponse:
    """La respuesta de usuario incluye sus permisos, para que el frontend muestre sólo lo que puede usar."""
    datos = UserResponse.model_validate(user)
    vigentes = permisos_de(user, db)
    datos.permisos = [PermisoResumen(codigo=p.codigo, nombre=p.nombre) for p in PERMISOS if p.codigo in vigentes]
    return datos


# ---------- API de administración de permisos ----------
router = APIRouter(prefix="/api", tags=["permisos"])
administrar = requiere("roles.administrar")


class PermisoOut(BaseModel):
    codigo: str
    modulo: str
    nombre: str
    descripcion: str
    delegable: bool
    en_desarrollo: bool


class PermisosRolOut(BaseModel):
    role_id: int
    codigo: str
    nombre: str
    editable: bool  # false: rol de fábrica o rol eliminado
    motivo: str | None = None
    permisos: list[str]


class PermisosRolIn(BaseModel):
    permisos: list[str] = Field(max_length=len(PERMISOS))


def _rol(db: Session, role_id: int) -> RoleDefinition:
    rol = db.get(RoleDefinition, role_id)
    if not rol:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El rol no existe")
    return rol


def permisos_del_rol(db: Session, rol: RoleDefinition) -> list[str]:
    """Permisos del rol en el orden del catálogo (los de fábrica, por el código; los personalizados, por la base)."""
    vigentes = PERMISOS_SISTEMA[Role(rol.code)] if rol.es_sistema else permisos_de_rol_personalizado(db, rol.id)
    return [p.codigo for p in PERMISOS if p.codigo in vigentes]


@router.get("/permisos", response_model=list[PermisoOut])
def catalogo_permisos(_: User = Depends(administrar)):
    return [PermisoOut(**p.__dict__) for p in PERMISOS]


@router.get("/roles/{role_id}/permisos", response_model=PermisosRolOut)
def ver_permisos_de_rol(role_id: int, db: Session = Depends(get_db), _: User = Depends(administrar)):
    rol = _rol(db, role_id)
    motivo = "Rol del sistema: sus permisos están definidos en el código" if rol.es_sistema else ("El rol está eliminado; restáurelo para editar sus permisos" if rol.bin_status == STATUS_ELIMINADO else None)
    return PermisosRolOut(role_id=rol.id, codigo=rol.code, nombre=rol.name, editable=motivo is None, motivo=motivo, permisos=permisos_del_rol(db, rol))


@router.put("/roles/{role_id}/permisos", response_model=PermisosRolOut)
def definir_permisos_de_rol(role_id: int, payload: PermisosRolIn, db: Session = Depends(get_db), _: User = Depends(administrar)):
    """Reemplaza el conjunto de permisos de un rol personalizado."""
    rol = _rol(db, role_id)
    if rol.es_sistema:
        raise HTTPException(status.HTTP_409_CONFLICT, "Es un rol del sistema: sus permisos están definidos en el código y no se pueden cambiar")
    if rol.bin_status == STATUS_ELIMINADO:
        raise HTTPException(status.HTTP_409_CONFLICT, "El rol está eliminado; restáurelo para editar sus permisos")
    pedidos = set(payload.permisos)
    desconocidos = sorted(pedidos - POR_CODIGO.keys())
    if desconocidos:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Permiso desconocido: {desconocidos[0]}")
    reservados = sorted(pedidos - DELEGABLES)
    if reservados:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"«{POR_CODIGO[reservados[0]].nombre}» está reservado al administrador y no se puede asignar a un rol personalizado")
    ids = {p.codigo: p.id for p in db.scalars(select(PermisoModel))}
    db.execute(delete(RolPermisoModel).where(RolPermisoModel.role_definition_id == rol.id))
    db.add_all(RolPermisoModel(role_definition_id=rol.id, permiso_id=ids[codigo]) for codigo in pedidos)
    db.commit()
    return PermisosRolOut(role_id=rol.id, codigo=rol.code, nombre=rol.name, editable=True, permisos=permisos_del_rol(db, rol))
