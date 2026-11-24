from datetime import date

from django.db import transaction
from django.utils import timezone

from .models import Lote, MovimientoStock, Stock, Ubicacion


def obtener_lotes_fefo(producto, ubicacion, cantidad_requerida):
    """Devuelve [(Stock, cantidad_a_tomar), ...] priorizando el lote con
    vencimiento más próximo, hasta cubrir cantidad_requerida. Lanza ValueError
    si el stock disponible en esa ubicación no alcanza."""
    stocks = (
        Stock.objects
        .filter(lote__producto=producto, ubicacion=ubicacion, cantidad__gt=0)
        .filter(lote__fecha_vencimiento__gte=timezone.localdate())
        .select_related('lote')
        .order_by('lote__fecha_vencimiento')
    )

    plan = []
    restante = cantidad_requerida
    for stock in stocks:
        if restante <= 0:
            break
        cantidad_tomar = min(stock.cantidad, restante)
        plan.append((stock, cantidad_tomar))
        restante -= cantidad_tomar

    if restante > 0:
        raise ValueError(
            f'Stock insuficiente en {Ubicacion(ubicacion).label}: faltan {restante} unidades de {producto.nombre}.'
        )
    return plan


@transaction.atomic
def traspasar_stock(lote, cantidad, usuario, observacion=''):
    """Mueve `cantidad` unidades de un lote específico de bodega a vitrina."""
    if cantidad <= 0:
        raise ValueError('La cantidad a traspasar debe ser mayor a 0.')
    origen = Stock.objects.select_for_update().get(lote=lote, ubicacion=Ubicacion.BODEGA)
    if origen.cantidad < cantidad:
        raise ValueError(f'Stock insuficiente en bodega para el lote {lote.numero_lote}.')

    origen.cantidad -= cantidad
    origen.save(update_fields=['cantidad'])

    destino, _ = Stock.objects.select_for_update().get_or_create(lote=lote, ubicacion=Ubicacion.VITRINA)
    destino.cantidad += cantidad
    destino.save(update_fields=['cantidad'])

    MovimientoStock.objects.create(
        lote=lote, tipo=MovimientoStock.Tipo.TRASPASO,
        ubicacion_origen=Ubicacion.BODEGA, ubicacion_destino=Ubicacion.VITRINA,
        cantidad=cantidad, usuario=usuario, observacion=observacion,
    )


@transaction.atomic
def traspasar_fefo(producto, cantidad, usuario, observacion=''):
    """Traspasa `cantidad` unidades de un producto de bodega a vitrina,
    tomando primero de los lotes con vencimiento más próximo (FEFO)."""
    plan = obtener_lotes_fefo(producto, Ubicacion.BODEGA, cantidad)
    for stock, cantidad_tomar in plan:
        traspasar_stock(stock.lote, cantidad_tomar, usuario, observacion)


@transaction.atomic
def registrar_ajuste(lote, ubicacion, cantidad_delta, usuario, motivo):
    """Corrige el stock de un lote en una ubicación (merma, conteo físico).
    cantidad_delta positivo = aparece stock; negativo = se pierde stock."""
    if cantidad_delta == 0:
        raise ValueError('El ajuste debe ser distinto de cero.')

    stock, _ = Stock.objects.select_for_update().get_or_create(lote=lote, ubicacion=ubicacion)
    nueva_cantidad = stock.cantidad + cantidad_delta
    if nueva_cantidad < 0:
        raise ValueError('El ajuste dejaría el stock en negativo.')

    stock.cantidad = nueva_cantidad
    stock.save(update_fields=['cantidad'])

    es_positivo = cantidad_delta > 0
    MovimientoStock.objects.create(
        lote=lote,
        tipo=MovimientoStock.Tipo.AJUSTE_POSITIVO if es_positivo else MovimientoStock.Tipo.AJUSTE_NEGATIVO,
        ubicacion_destino=ubicacion if es_positivo else None,
        ubicacion_origen=None if es_positivo else ubicacion,
        cantidad=abs(cantidad_delta), usuario=usuario, observacion=motivo,
    )


@transaction.atomic
def descontar_venta_fefo(producto, cantidad, usuario, observacion=''):
    """Descuenta `cantidad` unidades de un producto en vitrina para una venta,
    tomando primero de los lotes con vencimiento más próximo. Devuelve
    [(Lote, cantidad_tomada), ...] para que ventas registre de qué lote
    exacto salió cada unidad (y pueda reintegrarlo si la venta se anula)."""
    plan = obtener_lotes_fefo(producto, Ubicacion.VITRINA, cantidad)
    consumo = []
    for stock, cantidad_tomar in plan:
        stock = Stock.objects.select_for_update().get(pk=stock.pk)
        stock.cantidad -= cantidad_tomar
        stock.save(update_fields=['cantidad'])

        MovimientoStock.objects.create(
            lote=stock.lote, tipo=MovimientoStock.Tipo.SALIDA_VENTA,
            ubicacion_origen=Ubicacion.VITRINA, cantidad=cantidad_tomar, usuario=usuario, observacion=observacion,
        )
        consumo.append((stock.lote, cantidad_tomar))
    return consumo


@transaction.atomic
def reintegrar_por_anulacion(lote, cantidad, usuario, observacion=''):
    """Devuelve `cantidad` unidades a vitrina para ese lote específico, al
    anular una venta que ya había descontado ese stock."""
    stock, _ = Stock.objects.select_for_update().get_or_create(lote=lote, ubicacion=Ubicacion.VITRINA)
    stock.cantidad += cantidad
    stock.save(update_fields=['cantidad'])

    MovimientoStock.objects.create(
        lote=lote, tipo=MovimientoStock.Tipo.DEVOLUCION_ANULACION,
        ubicacion_destino=Ubicacion.VITRINA, cantidad=cantidad, usuario=usuario, observacion=observacion,
    )


@transaction.atomic
def recibir_orden_compra(orden, usuario, fechas=None):
    """Marca la orden como recibida: crea/actualiza lotes y stock en bodega
    por cada línea, dejando registro en el ledger de movimientos."""
    orden = type(orden).objects.select_for_update().get(pk=orden.pk)
    if orden.estado != orden.Estado.PENDIENTE:
        raise ValueError('Solo se puede recibir una orden pendiente.')

    for detalle in orden.detalles.all():
        num_lote = (detalle.numero_lote or '').strip()
        if not num_lote:
            num_lote = f"L-{orden.pk:04d}-{detalle.producto.pk}"
            detalle.numero_lote = num_lote
            detalle.save(update_fields=['numero_lote'])

        fecha_venc = detalle.fecha_vencimiento
        campo = f'vencimiento_{detalle.pk}'
        if not fecha_venc or (fechas and campo in fechas):
            try:
                fecha_venc = date.fromisoformat((fechas or {}).get(campo, ''))
            except ValueError:
                raise ValueError(f'Ingresa el vencimiento del lote de {detalle.producto}.') from None
            detalle.fecha_vencimiento = fecha_venc
            detalle.save(update_fields=['fecha_vencimiento'])

        lote, _ = Lote.objects.get_or_create(
            producto=detalle.producto, numero_lote=num_lote,
            defaults={'fecha_vencimiento': fecha_venc},
        )
        if lote.fecha_vencimiento != fecha_venc:
            raise ValueError(f'El vencimiento indicado para el lote {num_lote} difiere del registrado.')
        stock, _ = Stock.objects.select_for_update().get_or_create(lote=lote, ubicacion=Ubicacion.BODEGA)
        stock.cantidad += detalle.cantidad
        stock.save(update_fields=['cantidad'])

        MovimientoStock.objects.create(
            lote=lote, tipo=MovimientoStock.Tipo.INGRESO_COMPRA,
            ubicacion_destino=Ubicacion.BODEGA, cantidad=detalle.cantidad, usuario=usuario,
            observacion=f'Recepción de {orden}',
        )

    orden.estado = orden.Estado.RECIBIDA
    orden.recibido_en = timezone.now()
    orden.save(update_fields=['estado', 'recibido_en'])
