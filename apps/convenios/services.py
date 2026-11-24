from django.utils import timezone

from .models import ClienteConvenio


def calcular_precio_con_descuento(cliente, producto):
    """Devuelve (precio_lista, precio_final, convenio, descuento_porcentaje).
    Si el cliente tiene varios convenios vigentes, se usa el que dé el mayor
    descuento para ese producto en particular."""
    precio_lista = producto.precio_venta

    if cliente is None:
        return precio_lista, precio_lista, None, 0

    hoy = timezone.localdate()
    afiliaciones = (
        ClienteConvenio.objects
        .filter(cliente=cliente, convenio__activo=True)
        .select_related('convenio')
    )

    mejor_convenio = None
    mejor_descuento = 0
    for afiliacion in afiliaciones:
        if not afiliacion.vigente(hoy):
            continue
        descuento = afiliacion.convenio.descuento_para(producto)
        if descuento > mejor_descuento:
            mejor_descuento = descuento
            mejor_convenio = afiliacion.convenio

    precio_final = round(precio_lista * (100 - mejor_descuento) / 100)
    return precio_lista, precio_final, mejor_convenio, mejor_descuento
