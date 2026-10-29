"""Reglas de validación del alta de taller (RFC, foto y datos del domicilio). El frontend replica las del RFC y la foto."""
import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, field_validator

# RFC: 3 letras (persona moral, 12 caracteres) o 4 (persona física, 13), fecha AAMMDD válida y homoclave de 3 caracteres.
RFC_REGEX = re.compile(r"^[A-ZÑ&]{3,4}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[A-Z0-9]{3}$")
DIAS_POR_MES = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)  # febrero admite 29: el RFC sólo trae 2 dígitos del año


def fecha_de_rfc_valida(rfc: str) -> bool:
    """La fecha AAMMDD del RFC debe existir en el calendario (p. ej. no hay 30 de febrero ni 31 de abril)."""
    cuerpo = rfc[3:] if rfc[3].isdigit() else rfc[4:]
    mes, dia = int(cuerpo[2:4]), int(cuerpo[4:6])
    return 1 <= mes <= 12 and 1 <= dia <= DIAS_POR_MES[mes - 1]


CP_REGEX = re.compile(r"^\d{5}$")
FOTO_MAX_BYTES = 15 * 1024 * 1024  # 15 MB

# Los formatos se identifican por su firma (bytes iniciales), no por la extensión ni el Content-Type que declare el navegador
FOTO_FIRMAS = (("jpg", lambda b: b[:3] == b"\xff\xd8\xff"), ("png", lambda b: b[:8] == b"\x89PNG\r\n\x1a\n"),
               ("webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"))


def tipo_de_foto(contenido: bytes) -> str | None:
    return next((nombre for nombre, coincide in FOTO_FIRMAS if coincide(contenido)), None)


def _limpiar(valor: object) -> object:
    return " ".join(valor.split()) if isinstance(valor, str) else valor


Texto = Annotated[str, BeforeValidator(_limpiar)]


class TallerIn(BaseModel):
    nombre: Texto = Field(min_length=3, max_length=100)
    rfc: str
    email_contacto: EmailStr
    calle: Texto = Field(min_length=3, max_length=150)
    colonia: Texto = Field(min_length=2, max_length=120)
    codigo_postal: str
    estado: Texto = Field(min_length=2, max_length=60)
    municipio: Texto = Field(min_length=2, max_length=100)

    @field_validator("rfc", mode="before")
    @classmethod
    def rfc_valido(cls, valor: object) -> str:
        rfc = str(valor or "").strip().upper()
        if not RFC_REGEX.match(rfc) or not fecha_de_rfc_valida(rfc):
            raise ValueError("El RFC no es válido: use 12 caracteres (persona moral) o 13 (persona física), por ejemplo ABC010203AB1")
        return rfc

    @field_validator("codigo_postal", mode="before")
    @classmethod
    def cp_valido(cls, valor: object) -> str:
        cp = str(valor or "").strip()
        if not CP_REGEX.match(cp):
            raise ValueError("El código postal debe tener 5 dígitos")
        return cp
