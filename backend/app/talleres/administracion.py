"""Administración de talleres: listar y buscar, editar datos y foto, y eliminar con borrado lógico (sólo `talleres.administrar`, el administrador).

Eliminar no borra el taller: cambia su `bin_status` al estatus «eliminado» y lo desactiva, de modo que sus empleados dejan de poder operar
clientes en él (la guarda `TallerActivo` lo rechaza) hasta que se restaure. Los clientes y la auditoría se conservan.
Si se cambia el nombre, las sucursales de los empleados que lo usaban se actualizan, porque el empleado se asocia al taller por ese nombre.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalogos import STATUS_ACTIVO, STATUS_ELIMINADO
from ..customers.modelos import AuditoriaModel, CustomerModel, TallerModel
from ..database import get_db
from ..models import User
from ..permisos import requiere
from .api import TallerOut, _duplicado, _leer_foto, _verificar_domicilio, carpeta_fotos
from .validaciones import FOTO_MAX_BYTES, TallerIn

router = APIRouter(prefix="/api/talleres", tags=["talleres"])
administrar = requiere("talleres.administrar")


class TallerAdminOut(TallerOut):
    bin_status: int
    empleados: int  # cuentas activas cuya sucursal coincide con el nombre del taller
    clientes: int
    created_at: datetime


class PaginaTalleres(BaseModel):
    items: list[TallerAdminOut]
    total: int
    pagina: int
    tamano: int


def _salida(db: Session, talleres: list[TallerModel]) -> list[TallerAdminOut]:
    if not talleres:
        return []
    clientes = dict(db.execute(select(CustomerModel.taller_id, func.count()).where(CustomerModel.taller_id.in_([t.id for t in talleres])).group_by(CustomerModel.taller_id)).all())
    nombres = [t.nombre.lower() for t in talleres]
    empleados = dict(db.execute(
        select(func.lower(User.branch), func.count()).where(User.bin_status == STATUS_ACTIVO, func.lower(User.branch).in_(nombres)).group_by(func.lower(User.branch))
    ).all())
    resultado = []
    for t in talleres:
        datos = TallerOut.model_validate(t).model_dump()
        datos["tiene_foto"] = bool(t.foto)
        resultado.append(TallerAdminOut(**datos, bin_status=t.bin_status, empleados=empleados.get(t.nombre.lower(), 0), clientes=clientes.get(t.id, 0), created_at=t.created_at))
    return resultado


def _existente(db: Session, taller_id: int) -> TallerModel:
    taller = db.get(TallerModel, taller_id)
    if not taller:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El taller no existe")
    return taller


def _auditar(db: Session, accion: str, usuario: User, taller: TallerModel, detalle: str) -> None:
    db.add(AuditoriaModel(accion=accion, usuario_id=usuario.id, taller_id=taller.id, customer_id=None, detalle=detalle[:250], fecha=datetime.utcnow()))


@router.get("/administracion", response_model=PaginaTalleres)
def listar_talleres_admin(
    buscar: str = Query("", max_length=100), incluir_eliminados: bool = Query(False), solo_eliminados: bool = Query(False),
    pagina: int = Query(1, ge=1), tamano: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db), _: User = Depends(administrar),
):
    """Talleres con búsqueda (nombre, RFC o municipio) y paginación. Por omisión no incluye los eliminados; `solo_eliminados` lista únicamente los suspendidos."""
    consulta = select(TallerModel)
    if solo_eliminados:
        consulta = consulta.where(TallerModel.bin_status == STATUS_ELIMINADO)
    elif not incluir_eliminados:
        consulta = consulta.where(TallerModel.bin_status == STATUS_ACTIVO)
    if buscar.strip():
        texto = buscar.strip().lower()
        consulta = consulta.where(
            func.lower(TallerModel.nombre).contains(texto, autoescape=True) | func.lower(TallerModel.rfc).contains(texto, autoescape=True)
            | func.lower(TallerModel.municipio).contains(texto, autoescape=True)
        )
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = list(db.scalars(consulta.order_by(func.lower(TallerModel.nombre), TallerModel.id).offset((pagina - 1) * tamano).limit(tamano)))
    return PaginaTalleres(items=_salida(db, filas), total=total, pagina=pagina, tamano=tamano)


@router.get("/{taller_id}", response_model=TallerAdminOut)
def ver_taller(taller_id: int, db: Session = Depends(get_db), _: User = Depends(administrar)):
    return _salida(db, [_existente(db, taller_id)])[0]


@router.put("/{taller_id}", response_model=TallerAdminOut)
def editar_taller(
    taller_id: int, request: Request,
    nombre: str = Form(""), rfc: str = Form(""), email_contacto: str = Form(""), calle: str = Form(""), colonia: str = Form(""),
    codigo_postal: str = Form(""), estado: str = Form(""), municipio: str = Form(""),
    foto: UploadFile | None = File(None),
    db: Session = Depends(get_db), usuario: User = Depends(administrar),
):
    """Reemplaza los datos del taller con las mismas reglas del alta. La foto es opcional: sin archivo se conserva la actual."""
    if int(request.headers.get("content-length") or 0) > FOTO_MAX_BYTES + 512 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La foto supera el máximo de 15 MB")
    taller = _existente(db, taller_id)
    if taller.bin_status != STATUS_ACTIVO:
        raise HTTPException(status.HTTP_409_CONFLICT, "El taller está eliminado; restáurelo para poder editarlo")
    try:
        datos = TallerIn(nombre=nombre, rfc=rfc, email_contacto=email_contacto, calle=calle, colonia=colonia,
                         codigo_postal=codigo_postal, estado=estado, municipio=municipio)
    except ValidationError as error:
        primero = error.errors()[0]
        campo = ".".join(str(p) for p in primero["loc"])
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{campo}: {primero['msg'].removeprefix('Value error, ')}")
    _verificar_domicilio(db, datos)
    if mensaje := _duplicado(db, datos, excluir_id=taller.id):
        raise HTTPException(status.HTTP_409_CONFLICT, mensaje)

    nueva = None
    if foto is not None and foto.filename:
        contenido, extension = _leer_foto(foto)
        nueva = carpeta_fotos() / f"{uuid.uuid4().hex}.{extension}"
        nueva.write_bytes(contenido)
    anterior, nombre_anterior = taller.foto, taller.nombre
    try:
        if datos.nombre != nombre_anterior:
            # Las sucursales de los empleados se enlazan al taller por su nombre: se renombran con él
            db.execute(update(User).where(func.lower(User.branch) == nombre_anterior.lower()).values(branch=datos.nombre))
        for campo, valor in datos.model_dump().items():
            setattr(taller, campo, valor)
        if nueva:
            taller.foto = nueva.name
        detalle = f"RFC {taller.rfc}" + (f"; antes «{nombre_anterior}»" if nombre_anterior != taller.nombre else "") + ("; foto nueva" if nueva else "")
        _auditar(db, "EDITAR_TALLER", usuario, taller, detalle)
        db.commit()
    except IntegrityError:
        db.rollback()
        if nueva:
            nueva.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un taller con ese nombre o RFC")
    except Exception:
        db.rollback()
        if nueva:
            nueva.unlink(missing_ok=True)  # no se queda una foto huérfana si el cambio falla
        raise
    if nueva and anterior:
        (carpeta_fotos() / anterior).unlink(missing_ok=True)  # la foto reemplazada ya no se usa
    db.refresh(taller)
    return _salida(db, [taller])[0]


@router.delete("/{taller_id}", response_model=TallerAdminOut)
def eliminar_taller(taller_id: int, db: Session = Depends(get_db), usuario: User = Depends(administrar)):
    """Borrado lógico: el taller y sus datos se conservan, pero deja de estar disponible para operar."""
    taller = _existente(db, taller_id)
    if taller.bin_status != STATUS_ACTIVO:
        raise HTTPException(status.HTTP_409_CONFLICT, "El taller ya está eliminado")
    taller.bin_status, taller.activo = STATUS_ELIMINADO, False
    _auditar(db, "ELIMINAR_TALLER", usuario, taller, f"RFC {taller.rfc}")
    db.commit()
    db.refresh(taller)
    return _salida(db, [taller])[0]


@router.post("/{taller_id}/restaurar", response_model=TallerAdminOut)
def restaurar_taller(taller_id: int, db: Session = Depends(get_db), usuario: User = Depends(administrar)):
    taller = _existente(db, taller_id)
    if taller.bin_status == STATUS_ACTIVO:
        raise HTTPException(status.HTTP_409_CONFLICT, "El taller no está eliminado")
    taller.bin_status, taller.activo = STATUS_ACTIVO, True
    _auditar(db, "RESTAURAR_TALLER", usuario, taller, f"RFC {taller.rfc}")
    db.commit()
    db.refresh(taller)
    return _salida(db, [taller])[0]
