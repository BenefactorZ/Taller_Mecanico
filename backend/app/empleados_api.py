"""Administración de empleados: listar y buscar cuentas, cambiar nombre, sucursal y rol, y eliminar con borrado lógico.

Sólo quien tiene el permiso `empleados.administrar` (el administrador). Incluye las cuentas Invitado: asignarles un rol las convierte en
empleados. Eliminar no borra la cuenta: cambia su `bin_status` al estatus «eliminado» y la desactiva (`is_active = 0`), de modo que ni
puede iniciar sesión ni recuperar su contraseña, y su sesión actual deja de valer en la siguiente petición. Restaurar la reactiva.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalogos import STATUS_ACTIVO, STATUS_ELIMINADO
from .customers.modelos import TallerModel
from .database import get_db
from .models import Role, RoleDefinition, User
from .permisos import requiere
from .roles_api import ROLES_SISTEMA, resolver_rol_empleado

router = APIRouter(prefix="/api/users", tags=["empleados"])
administrar = requiere("empleados.administrar")

# Cuentas que no se tocan desde esta pantalla: la del administrador y las internas
PROTEGIDOS = frozenset({Role.ADMINISTRADOR, Role.CLIENTE, Role.SISTEMA})
NOMBRES_SISTEMA = {codigo: nombre for codigo, nombre, _ in ROLES_SISTEMA}
CODIGOS_SISTEMA = {r.value for r in Role if r is not Role.PERSONALIZADO}


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str
    role: Role
    role_code: str  # código del rol que se muestra y se edita (el del rol personalizado, o el de fábrica)
    role_name: str
    branch: str | None
    is_active: bool
    bin_status: int
    protegido: bool
    es_usted: bool
    taller_registrado: bool | None  # ¿su sucursal coincide con un taller registrado? (None si no tiene sucursal)
    rol_eliminado: bool  # su rol personalizado fue eliminado: no le concede permisos
    created_at: datetime


class PaginaUsuarios(BaseModel):
    items: list[UsuarioOut]
    total: int
    pagina: int
    tamano: int


class UsuarioUpdate(BaseModel):
    full_name: str = Field(min_length=3, max_length=140, pattern=r".*\S.*")
    branch: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    role: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=40)


def _salida(db: Session, usuarios: list[User], usted: User) -> list[UsuarioOut]:
    talleres = {n.lower() for n in db.scalars(select(TallerModel.nombre).where(TallerModel.bin_status == STATUS_ACTIVO, TallerModel.activo == True))}  # noqa: E712
    resultado = []
    for u in usuarios:
        personalizado = u.role is Role.PERSONALIZADO and u.role_definition is not None
        resultado.append(UsuarioOut(
            id=u.id, full_name=u.full_name, email=u.email, role=u.role,
            role_code=u.role_definition.code if personalizado else u.role.value,
            role_name=u.role_definition.name if personalizado else NOMBRES_SISTEMA.get(u.role.value, u.role.value),
            branch=u.branch, is_active=u.is_active, bin_status=u.bin_status, protegido=u.role in PROTEGIDOS, es_usted=u.id == usted.id,
            taller_registrado=(u.branch.strip().lower() in talleres) if u.branch and u.branch.strip() else None,
            rol_eliminado=bool(personalizado and u.role_definition.bin_status != STATUS_ACTIVO), created_at=u.created_at,
        ))
    return resultado


def _modificable(db: Session, user_id: int, usted: User) -> User:
    destino = db.get(User, user_id)
    if not destino:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La cuenta no existe")
    if destino.id == usted.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puede modificar ni eliminar su propia cuenta desde aquí")
    if destino.role in PROTEGIDOS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Es una cuenta protegida (administrador o interna): no se administra desde aquí")
    return destino


@router.get("", response_model=PaginaUsuarios)
def listar_usuarios(
    buscar: str = Query("", max_length=100), rol: str = Query("", max_length=40), incluir_eliminados: bool = Query(False), solo_eliminados: bool = Query(False),
    pagina: int = Query(1, ge=1), tamano: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db), usted: User = Depends(administrar),
):
    """Cuentas con búsqueda (nombre o correo), filtro por rol y paginación. Por omisión no incluye las eliminadas; `solo_eliminados` lista únicamente las suspendidas."""
    consulta = select(User)
    if solo_eliminados:
        consulta = consulta.where(User.bin_status == STATUS_ELIMINADO)
    elif not incluir_eliminados:
        consulta = consulta.where(User.bin_status == STATUS_ACTIVO)
    if buscar.strip():
        texto = buscar.strip().lower()
        consulta = consulta.where(func.lower(User.full_name).contains(texto, autoescape=True) | func.lower(User.email).contains(texto, autoescape=True))
    if rol:
        if rol in CODIGOS_SISTEMA:
            consulta = consulta.where(User.role == Role(rol))
        else:
            personalizado = db.scalar(select(RoleDefinition.id).where(RoleDefinition.code == rol, RoleDefinition.es_sistema == False))  # noqa: E712
            consulta = consulta.where(User.role_definition_id == (personalizado or -1))
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = list(db.scalars(consulta.order_by(func.lower(User.full_name), User.id).offset((pagina - 1) * tamano).limit(tamano)).unique())
    return PaginaUsuarios(items=_salida(db, filas, usted), total=total, pagina=pagina, tamano=tamano)


@router.patch("/{user_id}", response_model=UsuarioOut)
def actualizar_usuario(user_id: int, payload: UsuarioUpdate, db: Session = Depends(get_db), usted: User = Depends(administrar)):
    """Cambia nombre, sucursal y rol. Con una cuenta Invitado, asignar un rol la convierte en empleado."""
    destino = _modificable(db, user_id, usted)
    if destino.bin_status != STATUS_ACTIVO:
        raise HTTPException(status.HTTP_409_CONFLICT, "La cuenta está eliminada; restáurela para poder editarla")
    rol, rol_id = resolver_rol_empleado(db, payload.role)
    destino.full_name = " ".join(payload.full_name.split())
    destino.branch = payload.branch.strip()
    destino.role, destino.role_definition_id = rol, rol_id
    db.commit()
    db.refresh(destino)
    return _salida(db, [destino], usted)[0]


@router.delete("/{user_id}", response_model=UsuarioOut)
def eliminar_usuario(user_id: int, db: Session = Depends(get_db), usted: User = Depends(administrar)):
    """Borrado lógico: la cuenta se conserva, pero deja de poder ingresar (también cierra su sesión actual)."""
    destino = _modificable(db, user_id, usted)
    destino.bin_status, destino.is_active = STATUS_ELIMINADO, False
    db.commit()
    db.refresh(destino)
    return _salida(db, [destino], usted)[0]


@router.post("/{user_id}/restaurar", response_model=UsuarioOut)
def restaurar_usuario(user_id: int, db: Session = Depends(get_db), usted: User = Depends(administrar)):
    destino = _modificable(db, user_id, usted)
    destino.bin_status, destino.is_active = STATUS_ACTIVO, True
    db.commit()
    db.refresh(destino)
    return _salida(db, [destino], usted)[0]
