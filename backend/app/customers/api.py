"""Endpoints de Clientes. La autorización vive en la cadena de guardas de la Facade (por permiso: clientes.alta y clientes.consultar)."""
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..catalogos import STATUS_ACTIVO
from ..database import get_db
from ..models import Role, User
from ..permisos import permisos_de
from ..security import current_user
from .dominio import ContextoSolicitud, DatosCliente, EstadoCustomer, ReglaIncumplida, ResultadoAlta, SolicitudPagina, Taller, Usuario
from .fachada import CustomerFacade
from .modelos import TallerModel
from .repositorio_sql import AuditoriaSqlRepositorio, CustomerSqlRepositorio

router = APIRouter(prefix="/api/customers", tags=["customers"])

ESTADO_HTTP = {
    "NO_AUTENTICADO": status.HTTP_401_UNAUTHORIZED,
    "NO_AUTORIZADO": status.HTTP_403_FORBIDDEN,
    "TALLER_INACTIVO": status.HTTP_403_FORBIDDEN,
    "FORMATO_INVALIDO": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "PAGINA_INVALIDA": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "NO_ENCONTRADO": status.HTTP_404_NOT_FOUND,
    "DUPLICADO": status.HTTP_409_CONFLICT,
    "COINCIDENCIA": status.HTTP_409_CONFLICT,  # mismo nombre que otro cliente del taller: se puede confirmar
    "CLIENTE_SUSPENDIDO": status.HTTP_409_CONFLICT,
    "ESTADO_INVALIDO": status.HTTP_409_CONFLICT,
}


def regla_incumplida_handler(_, error: ReglaIncumplida) -> JSONResponse:
    return JSONResponse(status_code=ESTADO_HTTP.get(error.codigo, status.HTTP_400_BAD_REQUEST), content={"detail": error.mensaje, "codigo": error.codigo})


class AltaIn(BaseModel):
    nombre_completo: str = Field(max_length=300)
    telefono: str = Field(max_length=60)
    correo: str = Field(max_length=300)
    confirmar: bool = False


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre_completo: str
    telefono: str | None
    correo: str | None
    taller_id: int
    estado: EstadoCustomer


class RespuestaAltaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resultado: ResultadoAlta
    customer: CustomerOut | None = None
    coincidencias: list[CustomerOut] = []


class PaginaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CustomerOut]
    total: int
    numero: int
    tamano: int
    hay_mas: bool


class AccesoOut(BaseModel):
    taller: str


def resolver_taller(db: Session, user: User) -> tuple[Taller, str]:
    """El Taller del usuario es el registrado cuyo nombre coincide con su sucursal (sin distinguir mayúsculas).

    Si la sucursal no está registrada, o el taller fue eliminado, no hay taller válido y la guarda lo rechaza.
    """
    nombre = (user.branch or "").strip()
    if not nombre:
        return Taller(0, False), "Sin taller"
    fila = db.scalar(select(TallerModel).where(func.lower(TallerModel.nombre) == nombre.lower(), TallerModel.bin_status == STATUS_ACTIVO))
    return (Taller(fila.id, fila.activo), fila.nombre) if fila else (Taller(0, False), nombre)


def contexto_solicitud(taller_id: int | None = Query(None, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db)) -> tuple[ContextoSolicitud, str]:
    """Taller de la solicitud: el de la sucursal de la persona. El administrador no tiene sucursal, así que elige el taller con `taller_id`."""
    if user.role is Role.ADMINISTRADOR:
        fila = db.scalar(select(TallerModel).where(TallerModel.id == taller_id, TallerModel.bin_status == STATUS_ACTIVO)) if taller_id else None
        taller, nombre = (Taller(fila.id, fila.activo), fila.nombre) if fila else (Taller(0, False), "Sin taller")
    else:
        taller, nombre = resolver_taller(db, user)
    return ContextoSolicitud(Usuario(user.id, user.role.value, True, permisos_de(user, db)), taller), nombre


def get_facade(db: Session = Depends(get_db)) -> CustomerFacade:
    return CustomerFacade(CustomerSqlRepositorio(db), AuditoriaSqlRepositorio(db))


@router.get("/alta/acceso", response_model=AccesoOut)
def abrir_alta(datos=Depends(contexto_solicitud), facade: CustomerFacade = Depends(get_facade)):
    """Paso «abrir alta»: sólo aplica las guardas antes de mostrar el formulario."""
    contexto, nombre_taller = datos
    facade.abrir_alta(contexto)
    return AccesoOut(taller=nombre_taller)


@router.post("", response_model=RespuestaAltaOut)
def alta_cliente(payload: AltaIn, response: Response, datos=Depends(contexto_solicitud), facade: CustomerFacade = Depends(get_facade), db: Session = Depends(get_db)):
    contexto, _ = datos
    try:
        respuesta = facade.AltaCliente(contexto, DatosCliente(payload.nombre_completo, payload.telefono, payload.correo), payload.confirmar)
    except Exception:
        db.rollback()
        raise
    db.commit()  # Customer y Auditoría se confirman juntos
    if respuesta.resultado is ResultadoAlta.CREADO:
        response.status_code = status.HTTP_201_CREATED
    return respuesta


@router.get("", response_model=PaginaOut)
def consultar_cliente(
    criterio: str = Query(min_length=1, max_length=140),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(10, ge=1, le=50),
    datos=Depends(contexto_solicitud),
    facade: CustomerFacade = Depends(get_facade),
):
    contexto, _ = datos
    return facade.ConsultarCliente(contexto, criterio, SolicitudPagina(pagina, tamano))


@router.get("/{customer_id}", response_model=CustomerOut)
def ficha_cliente(customer_id: int, datos=Depends(contexto_solicitud), facade: CustomerFacade = Depends(get_facade)):
    contexto, _ = datos
    return facade.obtener_ficha(contexto, customer_id)
