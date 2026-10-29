"""Roles: catálogo en base de datos (roles de fábrica + personalizados), administración con borrado lógico y asignación a empleados.

Los roles de fábrica (los del enum `Role`) se siembran en la tabla `role_definitions` con `es_sistema = 1`: aparecen en la administración
pero no se editan ni se eliminan, porque sus permisos están definidos en el código. Los personalizados los crea el administrador, se
editan, se eliminan lógicamente (`bin_status` → tabla `status`) y se restauran. Sólo el administrador.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .catalogos import STATUS_ACTIVO, STATUS_ELIMINADO, PermisoModel, RolPermisoModel
from .database import get_db
from .models import Role, RoleDefinition, User
from .schemas import RoleCreate, RoleResponse, RoleUpdate
from .permisos import DELEGABLES, PERMISOS, PERMISOS_SISTEMA, requiere

router = APIRouter(prefix="/api/roles", tags=["roles"])
solo_admin = requiere("roles.administrar")
asignador = requiere("empleados.alta")
# Se compara con == False: .is_(False) genera «IS 0», que SQL Server no admite
NO_SISTEMA = RoleDefinition.es_sistema == False  # noqa: E712

# (código, nombre, descripción) de los roles de fábrica que se muestran en la administración
ROLES_SISTEMA = (
    ("ADMINISTRADOR", "Administrador", "Administra el sistema: da de alta empleados, roles y talleres."),
    ("RECEPCIONISTA", "Recepcionista", "Registra y actualiza la información durante la recepción."),
    ("ASESOR_SERVICIO", "Asesor de servicio", "Consulta y corrige información de una orden."),
    ("TECNICO", "Técnico", "Actualiza y registra reparaciones o diagnósticos."),
    ("CLIENTE", "Cliente", "Recibe notificaciones sobre cambios del sistema o de su encargo."),
    ("SISTEMA", "Sistema", "Procesos internos automatizados."),
    ("INVITADO", "Invitado", "Cuenta autoregistrada: sin permisos hasta que un administrador le asigne un rol."),
)
# Roles de fábrica que se pueden asignar al dar de alta un empleado (el resto no son de empleado)
EMPLEADO_CODES = frozenset({"RECEPCIONISTA", "ASESOR_SERVICIO", "TECNICO"})
MENSAJE_SISTEMA = "Es un rol del sistema: sus permisos están definidos en el código, así que no se puede modificar ni eliminar"


def sembrar_roles_sistema(db: Session) -> None:
    """Deja los roles de fábrica en la tabla (idempotente). Se ejecuta al arrancar, después de las migraciones."""
    existentes = {r.code: r for r in db.scalars(select(RoleDefinition))}
    for codigo, nombre, descripcion in ROLES_SISTEMA:
        fila = existentes.get(codigo)
        if fila is None:
            db.add(RoleDefinition(code=codigo, name=nombre, description=descripcion, es_sistema=True, bin_status=STATUS_ACTIVO))
        elif not fila.es_sistema:
            fila.es_sistema = True
    db.commit()


def resolver_rol_empleado(db: Session, codigo: str) -> tuple[Role, int | None]:
    """Traduce el código elegido al dar de alta un empleado: (valor del enum Role, id del rol personalizado o None)."""
    if codigo in EMPLEADO_CODES:
        return Role(codigo), None
    if codigo in {r.value for r in Role}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ese rol del sistema no se asigna a empleados")
    rol = db.scalar(select(RoleDefinition).where(RoleDefinition.code == codigo, NO_SISTEMA, RoleDefinition.bin_status == STATUS_ACTIVO))
    if not rol:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El rol no existe o fue eliminado")
    return Role.PERSONALIZADO, rol.id


def _salida(db: Session, filas: list[RoleDefinition]) -> list[RoleResponse]:
    """Agrega a cada rol cuántos usuarios lo tienen (de fábrica: por el enum; personalizado: por role_definition_id)."""
    por_enum = dict(db.execute(select(User.role, func.count(User.id)).where(User.bin_status == STATUS_ACTIVO).group_by(User.role)).all())
    por_rol = dict(db.execute(select(User.role_definition_id, func.count(User.id)).where(User.role_definition_id.is_not(None), User.bin_status == STATUS_ACTIVO).group_by(User.role_definition_id)).all())
    asignados: dict[int, set[str]] = {}
    for rol_id, codigo in db.execute(select(RolPermisoModel.role_definition_id, PermisoModel.codigo).join(PermisoModel, PermisoModel.id == RolPermisoModel.permiso_id)):
        asignados.setdefault(rol_id, set()).add(codigo)
    resultado = []
    for fila in filas:
        datos = RoleResponse.model_validate(fila)
        datos.empleados = por_enum.get(Role(fila.code), 0) if fila.es_sistema else por_rol.get(fila.id, 0)
        vigentes = PERMISOS_SISTEMA[Role(fila.code)] if fila.es_sistema else asignados.get(fila.id, set()) & DELEGABLES
        datos.permisos = [p.codigo for p in PERMISOS if p.codigo in vigentes]
        resultado.append(datos)
    return resultado


def _rol(db: Session, role_id: int) -> RoleDefinition:
    rol = db.get(RoleDefinition, role_id)
    if not rol:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El rol no existe")
    return rol


def _modificable(db: Session, role_id: int) -> RoleDefinition:
    rol = _rol(db, role_id)
    if rol.es_sistema:
        raise HTTPException(status.HTTP_409_CONFLICT, MENSAJE_SISTEMA)
    return rol


def _nombre_repetido(db: Session, nombre: str, excepto_id: int | None = None) -> bool:
    consulta = select(RoleDefinition.id).where(func.lower(RoleDefinition.name) == nombre.strip().lower(), RoleDefinition.bin_status == STATUS_ACTIVO)
    if excepto_id:
        consulta = consulta.where(RoleDefinition.id != excepto_id)
    return db.scalar(consulta) is not None


@router.get("", response_model=list[RoleResponse])
def listar_roles(incluir_eliminados: bool = Query(False), db: Session = Depends(get_db), _: User = Depends(solo_admin)):
    """Todos los roles: primero los de fábrica y luego los personalizados."""
    consulta = select(RoleDefinition).order_by(RoleDefinition.es_sistema.desc(), RoleDefinition.name)
    if not incluir_eliminados:
        consulta = consulta.where(RoleDefinition.bin_status == STATUS_ACTIVO)
    return _salida(db, list(db.scalars(consulta)))


@router.get("/asignables", response_model=list[RoleResponse])
def roles_asignables(db: Session = Depends(get_db), _: User = Depends(asignador)):
    """Roles que se pueden elegir al dar de alta un empleado: los de empleado de fábrica y los personalizados activos."""
    consulta = (select(RoleDefinition)
                .where(RoleDefinition.bin_status == STATUS_ACTIVO, (NO_SISTEMA) | (RoleDefinition.code.in_(EMPLEADO_CODES)))
                .order_by(RoleDefinition.es_sistema.desc(), RoleDefinition.name))
    return _salida(db, list(db.scalars(consulta)))


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def crear_rol(payload: RoleCreate, db: Session = Depends(get_db), _: User = Depends(solo_admin)):
    existente = db.scalar(select(RoleDefinition).where(RoleDefinition.code == payload.code))
    if existente:
        detalle = "Ya existe un rol eliminado con esa clave; restáurelo desde la administración de roles" if existente.bin_status == STATUS_ELIMINADO else "Ya existe un rol con esa clave"
        raise HTTPException(status.HTTP_409_CONFLICT, detalle)
    if _nombre_repetido(db, payload.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un rol con ese nombre")
    rol = RoleDefinition(code=payload.code, name=payload.name.strip(), description=payload.description.strip() if payload.description else None)
    db.add(rol)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un rol con esa clave")
    db.refresh(rol)
    return _salida(db, [rol])[0]


@router.patch("/{role_id}", response_model=RoleResponse)
def actualizar_rol(role_id: int, payload: RoleUpdate, db: Session = Depends(get_db), _: User = Depends(solo_admin)):
    rol = _modificable(db, role_id)
    if rol.bin_status == STATUS_ELIMINADO:
        raise HTTPException(status.HTTP_409_CONFLICT, "El rol está eliminado; restáurelo para poder editarlo")
    if _nombre_repetido(db, payload.name, excepto_id=rol.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un rol con ese nombre")
    rol.name = payload.name.strip()
    rol.description = payload.description.strip() if payload.description else None
    db.commit()
    db.refresh(rol)
    return _salida(db, [rol])[0]


@router.delete("/{role_id}", response_model=RoleResponse)
def eliminar_rol(role_id: int, db: Session = Depends(get_db), _: User = Depends(solo_admin)):
    """Borrado lógico: no se elimina la fila, sólo cambia su `bin_status` al estatus «eliminado». Los empleados que lo tenían lo conservan."""
    rol = _modificable(db, role_id)
    rol.bin_status = STATUS_ELIMINADO
    db.commit()
    db.refresh(rol)
    return _salida(db, [rol])[0]


@router.post("/{role_id}/restaurar", response_model=RoleResponse)
def restaurar_rol(role_id: int, db: Session = Depends(get_db), _: User = Depends(solo_admin)):
    rol = _modificable(db, role_id)
    if _nombre_repetido(db, rol.name, excepto_id=rol.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede restaurar: ya existe otro rol activo con ese nombre")
    rol.bin_status = STATUS_ACTIVO
    db.commit()
    db.refresh(rol)
    return _salida(db, [rol])[0]
