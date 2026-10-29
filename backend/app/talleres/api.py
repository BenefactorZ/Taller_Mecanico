"""Alta de taller (sólo el administrador), consulta de talleres y catálogo de códigos postales para autollenar el domicilio."""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalogos import STATUS_ACTIVO, CodigoPostalModel
from ..config import settings
from ..customers.modelos import AuditoriaModel, TallerModel
from ..customers.normalizacion import normalizar_nombre
from ..database import get_db
from ..models import Role, User
from ..permisos import requiere
from .validaciones import CP_REGEX, FOTO_MAX_BYTES, TallerIn, tipo_de_foto

puede_consultar = requiere("talleres.consultar")
puede_dar_de_alta = requiere("talleres.alta")
router = APIRouter(prefix="/api/talleres", tags=["talleres"])
catalogo = APIRouter(prefix="/api/catalogos", tags=["catalogos"])


def carpeta_fotos() -> Path:
    base = Path(settings.uploads_dir) if settings.uploads_dir else Path(__file__).resolve().parents[2] / "uploads"
    carpeta = base / "talleres"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


class TallerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    rfc: str | None
    email_contacto: str | None
    calle: str | None
    colonia: str | None
    codigo_postal: str | None
    estado: str | None
    municipio: str | None
    tiene_foto: bool = False


def _salida(t: TallerModel) -> TallerOut:
    datos = TallerOut.model_validate(t)
    datos.tiene_foto = bool(t.foto)
    return datos


# ---------- Catálogo de códigos postales ----------

class ColoniaOut(BaseModel):
    colonia: str
    codigo_postal: str


class CodigoPostalOut(BaseModel):
    codigo_postal: str
    estado: str
    municipio: str
    colonias: list[str]


@catalogo.get("/estados", response_model=list[str])
def estados(db: Session = Depends(get_db), _: User = Depends(puede_dar_de_alta)):
    return list(db.scalars(select(CodigoPostalModel.estado).distinct().order_by(CodigoPostalModel.estado)))


@catalogo.get("/municipios", response_model=list[str])
def municipios(estado: str = Query(min_length=2), db: Session = Depends(get_db), _: User = Depends(puede_dar_de_alta)):
    return list(db.scalars(select(CodigoPostalModel.municipio).where(CodigoPostalModel.estado == estado).distinct().order_by(CodigoPostalModel.municipio)))


@catalogo.get("/colonias", response_model=list[ColoniaOut])
def colonias(estado: str = Query(min_length=2), municipio: str = Query(min_length=2), db: Session = Depends(get_db), _: User = Depends(puede_dar_de_alta)):
    """Camino inverso: al elegir la colonia se conoce su código postal."""
    filas = db.execute(
        select(CodigoPostalModel.colonia, CodigoPostalModel.codigo_postal)
        .where(CodigoPostalModel.estado == estado, CodigoPostalModel.municipio == municipio)
        .order_by(CodigoPostalModel.colonia, CodigoPostalModel.codigo_postal)
    )
    return [ColoniaOut(colonia=c, codigo_postal=cp) for c, cp in filas]


@catalogo.get("/codigo-postal/{cp}", response_model=CodigoPostalOut)
def por_codigo_postal(cp: str, db: Session = Depends(get_db), _: User = Depends(puede_dar_de_alta)):
    """Autollenado: con el código postal se conocen estado, municipio y colonias."""
    if not CP_REGEX.match(cp):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El código postal debe tener 5 dígitos")
    filas = list(db.scalars(select(CodigoPostalModel).where(CodigoPostalModel.codigo_postal == cp).order_by(CodigoPostalModel.colonia)))
    if not filas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos ese código postal; elija estado, municipio y colonia")
    return CodigoPostalOut(codigo_postal=cp, estado=filas[0].estado, municipio=filas[0].municipio, colonias=sorted({f.colonia for f in filas}))


def _verificar_domicilio(db: Session, datos: TallerIn) -> None:
    """El domicilio debe existir en el catálogo: el CP, el estado, el municipio y la colonia tienen que corresponderse."""
    filas = list(db.scalars(select(CodigoPostalModel).where(CodigoPostalModel.codigo_postal == datos.codigo_postal)))
    if not filas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El código postal no existe en el catálogo")
    base = filas[0]
    if normalizar_nombre(base.estado) != normalizar_nombre(datos.estado) or normalizar_nombre(base.municipio) != normalizar_nombre(datos.municipio):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El estado o el municipio no corresponden al código postal")
    if normalizar_nombre(datos.colonia) not in {normalizar_nombre(f.colonia) for f in filas}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La colonia no corresponde al código postal")


# ---------- Talleres ----------

def _leer_foto(foto: UploadFile) -> tuple[bytes, str]:
    contenido = bytearray()
    while trozo := foto.file.read(1024 * 1024):
        contenido += trozo
        if len(contenido) > FOTO_MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La foto supera el máximo de 15 MB")
    if not contenido:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Seleccione la foto del taller")
    tipo = tipo_de_foto(bytes(contenido[:16]))
    if not tipo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La foto debe ser JPG, PNG o WebP")
    return bytes(contenido), tipo


def _duplicado(db: Session, datos: TallerIn, excluir_id: int | None = None) -> str | None:
    """Taller único: no puede repetirse el nombre (sin distinguir mayúsculas) ni el RFC, ni siquiera frente a talleres eliminados.

    Al editar, `excluir_id` deja fuera al propio taller para que pueda conservar sus datos.
    """
    for campo, valor, etiqueta in ((func.lower(TallerModel.nombre), datos.nombre.lower(), "nombre"), (TallerModel.rfc, datos.rfc, "RFC")):
        fila = db.scalar(select(TallerModel).where(campo == valor, TallerModel.id != (excluir_id or 0)))
        if fila:
            sufijo = "; está eliminado, restáurelo en lugar de crearlo de nuevo" if fila.bin_status != STATUS_ACTIVO else ""
            return f"Ya existe un taller con ese {etiqueta}{sufijo}"
    return None


@router.get("", response_model=list[TallerOut])
def listar_talleres(db: Session = Depends(get_db), _: User = Depends(puede_consultar)):
    return [_salida(t) for t in db.scalars(select(TallerModel).where(TallerModel.bin_status == STATUS_ACTIVO).order_by(TallerModel.nombre))]


@router.post("", response_model=TallerOut, status_code=status.HTTP_201_CREATED)
def alta_taller(
    request: Request,
    nombre: str = Form(""), rfc: str = Form(""), email_contacto: str = Form(""), calle: str = Form(""), colonia: str = Form(""),
    codigo_postal: str = Form(""), estado: str = Form(""), municipio: str = Form(""),
    foto: UploadFile | None = File(None),
    db: Session = Depends(get_db), usuario: User = Depends(puede_dar_de_alta),
):
    # Antes de leer el archivo se descarta lo que ya declara pesar de más (la subida completa incluye los demás campos)
    if int(request.headers.get("content-length") or 0) > FOTO_MAX_BYTES + 512 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La foto supera el máximo de 15 MB")
    try:
        datos = TallerIn(nombre=nombre, rfc=rfc, email_contacto=email_contacto, calle=calle, colonia=colonia,
                         codigo_postal=codigo_postal, estado=estado, municipio=municipio)
    except ValidationError as error:
        primero = error.errors()[0]
        campo = ".".join(str(p) for p in primero["loc"])
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{campo}: {primero['msg'].removeprefix('Value error, ')}")
    if foto is None or not foto.filename:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Seleccione la foto del taller")
    _verificar_domicilio(db, datos)
    if mensaje := _duplicado(db, datos):
        raise HTTPException(status.HTTP_409_CONFLICT, mensaje)

    contenido, extension = _leer_foto(foto)
    archivo = f"{uuid.uuid4().hex}.{extension}"
    ruta = carpeta_fotos() / archivo
    ruta.write_bytes(contenido)
    try:
        taller = TallerModel(**datos.model_dump(), foto=archivo, activo=True, bin_status=STATUS_ACTIVO, created_by=usuario.id)
        db.add(taller)
        db.flush()
        db.add(AuditoriaModel(accion="ALTA_TALLER", usuario_id=usuario.id, taller_id=taller.id, customer_id=None, detalle=f"RFC {taller.rfc}", fecha=datetime.utcnow()))
        db.commit()
    except IntegrityError:
        db.rollback()
        ruta.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un taller con ese nombre o RFC")
    except Exception:
        db.rollback()
        ruta.unlink(missing_ok=True)  # no se queda una foto huérfana si el alta falla
        raise
    db.refresh(taller)
    return _salida(taller)


@router.get("/{taller_id}/foto")
def foto_taller(taller_id: int, db: Session = Depends(get_db), _: User = Depends(puede_consultar)):
    taller = db.get(TallerModel, taller_id)
    ruta = carpeta_fotos() / taller.foto if taller and taller.foto else None
    if not ruta or not ruta.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El taller no tiene foto")
    tipos = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    return FileResponse(ruta, media_type=tipos.get(ruta.suffix.lstrip("."), "application/octet-stream"))
