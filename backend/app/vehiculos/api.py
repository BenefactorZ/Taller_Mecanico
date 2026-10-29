"""Registro y consulta de vehículos (recepcionista y administrador), siempre asociados a un cliente.

Flujo del registro: **datos del vehículo → normalizar → duplicados → guardar → relacionar**, con el resultado «vehículo activo».
Todo ocurre en una sola transacción: si algún paso falla no queda ni el vehículo ni su foto.
"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalogos import STATUS_ACTIVO, STATUS_ELIMINADO
from ..config import settings
from ..customers.administracion import alcance_de, cliente_en_alcance
from ..customers.dominio import EstadoCustomer, ReglaIncumplida
from ..customers.modelos import AuditoriaModel, CustomerModel, TallerModel
from ..customers.normalizacion import normalizar_nombre
from ..database import get_db
from ..models import User
from ..permisos import requiere
from ..talleres.validaciones import FOTO_MAX_BYTES, tipo_de_foto
from .modelos import VehiculoModel
from .validaciones import VehiculoIn

router = APIRouter(prefix="/api/vehiculos", tags=["vehiculos"])
puede_registrar = requiere("vehiculos.registrar")
puede_consultar = requiere("vehiculos.consultar")


def carpeta_fotos() -> Path:
    base = Path(settings.uploads_dir) if settings.uploads_dir else Path(__file__).resolve().parents[2] / "uploads"
    carpeta = base / "vehiculos"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


class VehiculoOut(BaseModel):
    id: int
    customer_id: int
    cliente: str
    taller_id: int
    taller: str
    vin: str
    placa: str
    marca: str
    modelo: str
    anio: int
    color: str
    kilometraje: int | None
    tiene_foto: bool
    estado: str
    created_at: datetime


class PaginaVehiculos(BaseModel):
    items: list[VehiculoOut]
    total: int
    pagina: int
    tamano: int


def _salida(db: Session, filas: list[VehiculoModel]) -> list[VehiculoOut]:
    if not filas:
        return []
    clientes = dict(db.execute(select(CustomerModel.id, CustomerModel.nombre_completo).where(CustomerModel.id.in_({v.customer_id for v in filas}))).all())
    talleres = dict(db.execute(select(TallerModel.id, TallerModel.nombre).where(TallerModel.id.in_({v.taller_id for v in filas}))).all())
    return [VehiculoOut(id=v.id, customer_id=v.customer_id, cliente=clientes.get(v.customer_id, ""), taller_id=v.taller_id, taller=talleres.get(v.taller_id, ""),
                        vin=v.vin, placa=v.placa, marca=v.marca, modelo=v.modelo, anio=v.anio, color=v.color, kilometraje=v.kilometraje,
                        tiene_foto=bool(v.foto), estado="ACTIVO" if v.bin_status == STATUS_ACTIVO else "ELIMINADO", created_at=v.created_at) for v in filas]


# ---------- pasos del flujo de registro ----------

def _normalizar(**campos: str) -> VehiculoIn:
    """Paso 2. Normaliza (mayúsculas y sin separadores en VIN y placa, textos limpios) y valida con las expresiones regulares."""
    try:
        return VehiculoIn(**campos)
    except ValidationError as error:
        primero = error.errors()[0]
        campo = ".".join(str(p) for p in primero["loc"])
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{campo}: {primero['msg'].removeprefix('Value error, ')}")


def _verificar_duplicados(db: Session, datos: VehiculoIn) -> None:
    """Paso 3. El VIN identifica al vehículo y la placa a quien lo circula: ninguno puede repetirse."""
    if db.scalar(select(VehiculoModel.id).where(VehiculoModel.vin == datos.vin)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un vehículo registrado con ese VIN")
    if db.scalar(select(VehiculoModel.id).where(VehiculoModel.placa == datos.placa)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un vehículo registrado con esa placa")


def _leer_foto(foto: UploadFile) -> tuple[bytes, str]:
    contenido = bytearray()
    while trozo := foto.file.read(1024 * 1024):
        contenido += trozo
        if len(contenido) > FOTO_MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La imagen supera el máximo de 15 MB")
    if not contenido:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Seleccione la imagen del vehículo")
    tipo = tipo_de_foto(bytes(contenido[:16]))
    if not tipo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La imagen debe ser JPG, PNG o WebP")
    return bytes(contenido), tipo


def _guardar(db: Session, datos: VehiculoIn, cliente: CustomerModel, usuario: User, archivo: str) -> VehiculoModel:
    """Paso 4. Crea el vehículo activo con la imagen ya almacenada."""
    vehiculo = VehiculoModel(customer_id=cliente.id, taller_id=cliente.taller_id, foto=archivo, bin_status=STATUS_ACTIVO, created_by=usuario.id, **datos.model_dump())
    db.add(vehiculo)
    db.flush()
    return vehiculo


def _relacionar(db: Session, vehiculo: VehiculoModel, cliente: CustomerModel, usuario: User) -> None:
    """Paso 5. Deja constancia del vínculo cliente ↔ vehículo en la auditoría (aparece en el historial del cliente)."""
    db.add(AuditoriaModel(accion="ALTA_VEHICULO", usuario_id=usuario.id, taller_id=cliente.taller_id, customer_id=cliente.id,
                          detalle=f"Vehículo #{vehiculo.id}: {vehiculo.marca} {vehiculo.modelo} {vehiculo.anio}, placa {vehiculo.placa}, VIN {vehiculo.vin}"[:250], fecha=datetime.utcnow()))


@router.post("", response_model=VehiculoOut, status_code=status.HTTP_201_CREATED)
def registrar_vehiculo(
    request: Request,
    customer_id: int = Form(0), vin: str = Form(""), placa: str = Form(""), marca: str = Form(""), modelo: str = Form(""),
    anio: str = Form(""), color: str = Form(""), kilometraje: str = Form(""),
    foto: UploadFile | None = File(None),
    db: Session = Depends(get_db), usuario: User = Depends(puede_registrar),
):
    # 1 · Datos del vehículo: antes de leer el archivo se descarta lo que ya declara pesar de más, y se comprueba el cliente
    if int(request.headers.get("content-length") or 0) > FOTO_MAX_BYTES + 512 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La imagen supera el máximo de 15 MB")
    if customer_id < 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "customer_id: seleccione el cliente al que pertenece el vehículo")
    cliente = cliente_en_alcance(db, usuario, customer_id)
    if cliente.estado is EstadoCustomer.INACTIVO:
        raise ReglaIncumplida("CLIENTE_SUSPENDIDO", "El cliente está suspendido; no se le pueden registrar vehículos")
    # 2 · Normalizar
    datos = _normalizar(vin=vin, placa=placa, marca=marca, modelo=modelo, anio=anio, color=color, kilometraje=kilometraje)
    if foto is None or not foto.filename:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Seleccione la imagen del vehículo")
    # 3 · Duplicados
    _verificar_duplicados(db, datos)
    # 4 · Guardar (con la imagen) y 5 · Relacionar con el cliente, en una sola transacción
    contenido, extension = _leer_foto(foto)
    ruta = carpeta_fotos() / f"{uuid.uuid4().hex}.{extension}"
    ruta.write_bytes(contenido)
    try:
        vehiculo = _guardar(db, datos, cliente, usuario, ruta.name)
        _relacionar(db, vehiculo, cliente, usuario)
        db.commit()
    except IntegrityError:
        db.rollback()
        ruta.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un vehículo con ese VIN o esa placa")
    except Exception:
        db.rollback()
        ruta.unlink(missing_ok=True)  # no se queda una imagen huérfana si el registro falla
        raise
    db.refresh(vehiculo)
    return _salida(db, [vehiculo])[0]


@router.get("", response_model=PaginaVehiculos)
def listar_vehiculos(
    buscar: str = Query("", max_length=100), customer_id: int | None = Query(None, ge=1), estado: str = Query("ACTIVO", pattern=r"^(ACTIVO|ELIMINADO)$"),
    pagina: int = Query(1, ge=1), tamano: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db), usuario: User = Depends(puede_consultar),
):
    """Vehículos con búsqueda (placa, VIN, marca, modelo o nombre del cliente). Cada persona ve los de su taller; el administrador, todos.

    Por omisión sólo los activos; con `estado=ELIMINADO` se listan los dados de baja para poder restaurarlos.
    """
    limite = alcance_de(db, usuario)
    consulta = select(VehiculoModel).join(CustomerModel, CustomerModel.id == VehiculoModel.customer_id).where(VehiculoModel.bin_status == (STATUS_ACTIVO if estado == "ACTIVO" else STATUS_ELIMINADO))
    if limite is not None:
        consulta = consulta.where(VehiculoModel.taller_id == limite)
    if customer_id:
        consulta = consulta.where(VehiculoModel.customer_id == customer_id)
    if buscar.strip():
        texto = buscar.strip()
        codigo = texto.upper().replace(" ", "").replace("-", "")
        consulta = consulta.where(
            VehiculoModel.placa.contains(codigo, autoescape=True) | VehiculoModel.vin.contains(codigo, autoescape=True)
            | func.lower(VehiculoModel.marca).contains(texto.lower(), autoescape=True) | func.lower(VehiculoModel.modelo).contains(texto.lower(), autoescape=True)
            | CustomerModel.nombre_clave.contains(normalizar_nombre(texto), autoescape=True)
        )
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = list(db.scalars(consulta.order_by(VehiculoModel.id.desc()).offset((pagina - 1) * tamano).limit(tamano)))
    return PaginaVehiculos(items=_salida(db, filas), total=total, pagina=pagina, tamano=tamano)


# ---------- consulta, modificación, baja lógica y restauración ----------

CAMPOS = ("vin", "placa", "marca", "modelo", "anio", "color", "kilometraje")
ETIQUETAS = {"vin": "VIN", "placa": "placa", "marca": "marca", "modelo": "modelo", "anio": "año", "color": "color", "kilometraje": "kilometraje"}


def vehiculo_en_alcance(db: Session, usuario: User, vehiculo_id: int) -> VehiculoModel:
    """El vehículo, si existe y es de un taller que la persona puede ver. Fuera de su alcance responde 404 (no revela que existe)."""
    vehiculo = db.get(VehiculoModel, vehiculo_id)
    limite = alcance_de(db, usuario)
    if vehiculo is None or (limite is not None and vehiculo.taller_id != limite):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El vehículo no existe")
    return vehiculo


def _auditar(db: Session, accion: str, usuario: User, vehiculo: VehiculoModel, detalle: str) -> None:
    db.add(AuditoriaModel(accion=accion, usuario_id=usuario.id, taller_id=vehiculo.taller_id, customer_id=vehiculo.customer_id, detalle=detalle[:250], fecha=datetime.utcnow()))


def _valor(valor: object) -> str:
    return "sin dato" if valor in (None, "") else str(valor)


@router.get("/{vehiculo_id}", response_model=VehiculoOut)
def obtener_vehiculo(vehiculo_id: int, db: Session = Depends(get_db), usuario: User = Depends(puede_consultar)):
    return _salida(db, [vehiculo_en_alcance(db, usuario, vehiculo_id)])[0]


@router.put("/{vehiculo_id}", response_model=VehiculoOut)
def modificar_vehiculo(
    vehiculo_id: int, request: Request,
    vin: str = Form(""), placa: str = Form(""), marca: str = Form(""), modelo: str = Form(""), anio: str = Form(""), color: str = Form(""), kilometraje: str = Form(""),
    foto: UploadFile | None = File(None),
    db: Session = Depends(get_db), usuario: User = Depends(puede_registrar),
):
    """Modifica los datos de un vehículo activo (la imagen es opcional: si no se envía se conserva). El cliente y el taller no cambian."""
    if int(request.headers.get("content-length") or 0) > FOTO_MAX_BYTES + 512 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La imagen supera el máximo de 15 MB")
    vehiculo = vehiculo_en_alcance(db, usuario, vehiculo_id)
    if vehiculo.bin_status != STATUS_ACTIVO:
        raise ReglaIncumplida("ESTADO_INVALIDO", "El vehículo está eliminado; restáurelo para poder modificarlo")
    datos = _normalizar(vin=vin, placa=placa, marca=marca, modelo=modelo, anio=anio, color=color, kilometraje=kilometraje)
    # duplicados: el VIN y la placa no pueden ser de otro vehículo (eliminados incluidos, porque siguen ocupando el valor)
    if db.scalar(select(VehiculoModel.id).where(VehiculoModel.vin == datos.vin, VehiculoModel.id != vehiculo.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un vehículo registrado con ese VIN")
    if db.scalar(select(VehiculoModel.id).where(VehiculoModel.placa == datos.placa, VehiculoModel.id != vehiculo.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un vehículo registrado con esa placa")
    nueva: Path | None = None
    if foto is not None and foto.filename:
        contenido, extension = _leer_foto(foto)
        nueva = carpeta_fotos() / f"{uuid.uuid4().hex}.{extension}"
        nueva.write_bytes(contenido)
    cambios = [f"{ETIQUETAS[c]} de «{_valor(getattr(vehiculo, c))}» a «{_valor(getattr(datos, c))}»" for c in CAMPOS if getattr(vehiculo, c) != getattr(datos, c)]
    if nueva:
        cambios.append("imagen")
    anterior = vehiculo.foto
    try:
        if cambios:
            for campo in CAMPOS:
                setattr(vehiculo, campo, getattr(datos, campo))
            if nueva:
                vehiculo.foto = nueva.name
            _auditar(db, "ACTUALIZAR_VEHICULO", usuario, vehiculo, f"Vehículo #{vehiculo.id}: " + "; ".join(cambios))
            db.commit()
    except IntegrityError:
        db.rollback()
        if nueva:
            nueva.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un vehículo con ese VIN o esa placa")
    except Exception:
        db.rollback()
        if nueva:
            nueva.unlink(missing_ok=True)
        raise
    if nueva and anterior:
        (carpeta_fotos() / anterior).unlink(missing_ok=True)  # la imagen reemplazada ya no se necesita
    db.refresh(vehiculo)
    return _salida(db, [vehiculo])[0]


@router.delete("/{vehiculo_id}", response_model=VehiculoOut)
def eliminar_vehiculo(vehiculo_id: int, db: Session = Depends(get_db), usuario: User = Depends(puede_registrar)):
    """Borrado lógico: el vehículo deja de listarse pero se conserva (y puede restaurarse). La imagen no se borra."""
    vehiculo = vehiculo_en_alcance(db, usuario, vehiculo_id)
    if vehiculo.bin_status != STATUS_ACTIVO:
        raise ReglaIncumplida("ESTADO_INVALIDO", "El vehículo ya está eliminado")
    vehiculo.bin_status = STATUS_ELIMINADO
    _auditar(db, "ELIMINAR_VEHICULO", usuario, vehiculo, f"Vehículo #{vehiculo.id}: {vehiculo.marca} {vehiculo.modelo}, placa {vehiculo.placa}")
    db.commit()
    db.refresh(vehiculo)
    return _salida(db, [vehiculo])[0]


@router.post("/{vehiculo_id}/restaurar", response_model=VehiculoOut)
def restaurar_vehiculo(vehiculo_id: int, db: Session = Depends(get_db), usuario: User = Depends(puede_registrar)):
    vehiculo = vehiculo_en_alcance(db, usuario, vehiculo_id)
    if vehiculo.bin_status == STATUS_ACTIVO:
        raise ReglaIncumplida("ESTADO_INVALIDO", "El vehículo ya está activo")
    dueno = db.get(CustomerModel, vehiculo.customer_id)
    if dueno is None or dueno.estado is EstadoCustomer.INACTIVO:
        raise ReglaIncumplida("CLIENTE_SUSPENDIDO", "El cliente está suspendido; reactívelo antes de restaurar su vehículo")
    vehiculo.bin_status = STATUS_ACTIVO
    _auditar(db, "RESTAURAR_VEHICULO", usuario, vehiculo, f"Vehículo #{vehiculo.id}: {vehiculo.marca} {vehiculo.modelo}, placa {vehiculo.placa}")
    db.commit()
    db.refresh(vehiculo)
    return _salida(db, [vehiculo])[0]


@router.get("/{vehiculo_id}/foto")
def foto_vehiculo(vehiculo_id: int, db: Session = Depends(get_db), usuario: User = Depends(puede_consultar)):
    vehiculo = db.get(VehiculoModel, vehiculo_id)
    limite = alcance_de(db, usuario)
    if vehiculo is None or (limite is not None and vehiculo.taller_id != limite):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El vehículo no existe")
    ruta = carpeta_fotos() / vehiculo.foto if vehiculo.foto else None
    if not ruta or not ruta.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El vehículo no tiene imagen")
    tipos = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    return FileResponse(ruta, media_type=tipos.get(ruta.suffix.lstrip("."), "application/octet-stream"))
