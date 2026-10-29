"""Normalización y validación de los datos de un vehículo. El frontend replica las expresiones regulares (frontend/src/vehiculos.ts)."""
import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

# VIN (ISO 3779): 17 caracteres alfanuméricos; las letras I, O y Q no se usan para no confundirlas con 1 y 0.
VIN_REGEX = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
# Placa mexicana ya normalizada (mayúsculas, sin guiones ni espacios): 5 a 7 caracteres que combinan letras y números (p. ej. ABC123D, 123ABC).
PLACA_REGEX = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9]{5,7}$")
ANIO_MINIMO = 1981  # el VIN de 17 caracteres es obligatorio desde el modelo 1981
KILOMETRAJE_MAXIMO = 2_000_000


def normalizar_codigo(valor: object) -> str:
    """VIN y placa se comparan y guardan en mayúsculas y sin espacios, guiones ni puntos."""
    return re.sub(r"[\s.\-]", "", str(valor or "")).upper()


def normalizar_texto(valor: object) -> str:
    """Quita espacios sobrantes. Si todo está en minúsculas, capitaliza cada palabra; si ya trae mayúsculas (BMW, CX-5) se respeta."""
    texto = " ".join(str(valor or "").split())
    return texto.title() if texto and texto == texto.lower() else texto


def _kilometraje_vacio(valor: object) -> object:
    return None if valor is None or (isinstance(valor, str) and not valor.strip()) else valor


Texto = Annotated[str, BeforeValidator(normalizar_texto)]


class VehiculoIn(BaseModel):
    vin: str
    placa: str
    marca: Texto = Field(min_length=2, max_length=40)
    modelo: Texto = Field(min_length=1, max_length=60)
    anio: int
    color: Texto = Field(min_length=3, max_length=30)
    kilometraje: Annotated[int | None, BeforeValidator(_kilometraje_vacio)] = Field(default=None, ge=0, le=KILOMETRAJE_MAXIMO)

    @field_validator("vin", mode="before")
    @classmethod
    def vin_valido(cls, valor: object) -> str:
        vin = normalizar_codigo(valor)
        if not VIN_REGEX.match(vin):
            raise ValueError("El VIN debe tener 17 caracteres (letras y números, sin I, O ni Q), por ejemplo 1HGCM82633A004352")
        return vin

    @field_validator("placa", mode="before")
    @classmethod
    def placa_valida(cls, valor: object) -> str:
        placa = normalizar_codigo(valor)
        if not PLACA_REGEX.match(placa):
            raise ValueError("La placa debe tener de 5 a 7 caracteres entre letras y números, por ejemplo ABC-123-D")
        return placa

    @field_validator("anio")
    @classmethod
    def anio_valido(cls, valor: int) -> int:
        maximo = date.today().year + 1
        if not ANIO_MINIMO <= valor <= maximo:
            raise ValueError(f"El año debe estar entre {ANIO_MINIMO} y {maximo}")
        return valor
