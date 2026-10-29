"""Normalización y validación de formato, compartidas por el alta y la consulta."""
import re
import unicodedata

from .dominio import DatosCliente, DatosNormalizados, ReglaIncumplida

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def limpiar_nombre(valor: str) -> str:
    """Nombre para mostrar y guardar: sin espacios sobrantes, respetando mayúsculas y acentos."""
    return " ".join(valor.split())


def normalizar_nombre(valor: str) -> str:
    """Clave de comparación: sin acentos ni mayúsculas, para que 'María' y 'maria' coincidan."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", limpiar_nombre(valor)) if not unicodedata.combining(c))
    return sin_acentos.casefold()


def normalizar_contacto(valor: str) -> str:
    texto = valor.strip()
    if "@" in texto:
        return texto.casefold()
    return re.sub(r"[\s().-]", "", texto)


def normalizar_telefono(valor: str) -> str:
    """Teléfono sin espacios, paréntesis, puntos ni guiones (se conserva un + inicial)."""
    return re.sub(r"[\s().-]", "", valor.strip())


def normalizar_correo(valor: str) -> str:
    return valor.strip().casefold()


def normalizar_criterio(valor: str) -> str:
    """Un criterio de consulta puede ser un nombre o un contacto; se normaliza como contacto si lo parece."""
    texto = valor.strip()
    return normalizar_contacto(texto) if es_contacto(texto) else normalizar_nombre(texto)


def es_contacto(valor: str) -> bool:
    texto = valor.strip()
    return "@" in texto or bool(re.fullmatch(r"\+?[\d\s().-]{7,}", texto))


def normalizar_y_validar(datos: DatosCliente) -> DatosNormalizados:
    nombre = limpiar_nombre(datos.nombre_completo)
    telefono = normalizar_telefono(datos.telefono)
    correo = normalizar_correo(datos.correo)
    if len(nombre) > 140:
        raise ReglaIncumplida("FORMATO_INVALIDO", "El nombre admite hasta 140 caracteres")
    if len(nombre.split()) < 2 or len(nombre) < 3:
        raise ReglaIncumplida("FORMATO_INVALIDO", "Ingrese el nombre completo (nombre y apellido)")
    if not telefono:
        raise ReglaIncumplida("FORMATO_INVALIDO", "Ingrese el teléfono")
    if not re.fullmatch(r"\+?\d{10,15}", telefono):
        raise ReglaIncumplida("FORMATO_INVALIDO", "El teléfono debe tener de 10 a 15 dígitos")
    if not correo:
        raise ReglaIncumplida("FORMATO_INVALIDO", "Ingrese el correo")
    if len(correo) > 254 or not _CORREO.match(correo):
        raise ReglaIncumplida("FORMATO_INVALIDO", "El correo no tiene un formato válido")
    return DatosNormalizados(nombre, telefono, correo)
