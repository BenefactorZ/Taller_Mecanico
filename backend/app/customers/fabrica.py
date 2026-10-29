"""Patrón Factory Method: único punto de creación de Customer, invocado sólo cuando la política autoriza crear."""
from abc import ABC, abstractmethod

from .dominio import Customer, DatosNormalizados, EstadoCustomer, ReglaIncumplida, Taller


class CustomerCreator(ABC):
    """Creator: define el flujo de creación y deja la construcción al factory method `_nuevo_customer`."""

    def crear(self, datos: DatosNormalizados, taller: Taller) -> Customer:
        customer = self._nuevo_customer(datos, taller)
        if customer.estado is not EstadoCustomer.ACTIVO:
            raise ReglaIncumplida("CUSTOMER_NO_ACTIVO", "Un Customer recién creado debe quedar activo")
        return customer

    @abstractmethod
    def _nuevo_customer(self, datos: DatosNormalizados, taller: Taller) -> Customer: ...


class CustomerActivoCreator(CustomerCreator):
    """ConcreteCreator: construye el Customer activo con nombre, teléfono y correo ya normalizados."""

    def _nuevo_customer(self, datos: DatosNormalizados, taller: Taller) -> Customer:
        return Customer(None, datos.nombre_completo, datos.telefono, datos.correo, taller.id, EstadoCustomer.ACTIVO)
