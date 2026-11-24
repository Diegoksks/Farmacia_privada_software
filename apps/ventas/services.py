from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.convenios import services as convenios_services
from apps.inventario import services as inventario_services
from apps.recetas import services as recetas_services

from .models import Caja, DocumentoTributario, Venta, VentaDetalle, VentaDetalleLote


@transaction.atomic
def abrir_caja(usuario, monto_apertura):
    if Caja.objects.filter(usuario=usuario, fecha_cierre__isnull=True).exists():
        raise ValueError('Ya tienes una caja abierta.')
    return Caja.objects.create(usuario=usuario, monto_apertura=monto_apertura)


@transaction.atomic
def cerrar_caja(caja, monto_declarado, usuario):
    if not caja.esta_abierta:
        raise ValueError('Esta caja ya está cerrada.')

    monto_sistema = caja.calcular_monto_sistema()
    caja.monto_cierre_declarado = monto_declarado
    caja.monto_cierre_sistema = monto_sistema
    caja.diferencia = monto_declarado - monto_sistema
    caja.fecha_cierre = timezone.now()
    caja.save(update_fields=['monto_cierre_declarado', 'monto_cierre_sistema', 'diferencia', 'fecha_cierre'])
    return caja


@transaction.atomic
def registrar_venta(caja, vendedor, metodo_pago, lineas, cliente=None):
    """lineas: [{'producto', 'cantidad', 'receta_detalle' (opcional)}, ...].
    Cada línea descuenta stock de vitrina por FEFO y, si corresponde,
    saldo de receta — reutilizando los servicios ya construidos."""
    if not caja.esta_abierta:
        raise ValueError('La caja está cerrada.')
    if not lineas:
        raise ValueError('La venta no tiene productos.')

    venta = Venta.objects.create(caja=caja, cliente=cliente, vendedor=vendedor, metodo_pago=metodo_pago)

    for linea in lineas:
        producto = linea['producto']
        cantidad = linea['cantidad']
        receta_detalle = linea.get('receta_detalle')

        if not producto.activo:
            raise ValueError(f'{producto.nombre} está desactivado y no se puede vender.')
        if producto.requiere_receta and not receta_detalle:
            raise ValueError(f'{producto.nombre} requiere una receta con saldo disponible.')
        if receta_detalle and receta_detalle.producto_id != producto.id:
            raise ValueError('La receta seleccionada no corresponde a este producto.')

        precio_lista, precio_final, convenio, _ = convenios_services.calcular_precio_con_descuento(cliente, producto)
        detalle = VentaDetalle.objects.create(
            venta=venta, producto=producto, cantidad=cantidad,
            precio_lista=precio_lista, precio_unitario=precio_final, convenio=convenio,
            receta_detalle=receta_detalle,
        )

        consumo = inventario_services.descontar_venta_fefo(
            producto, cantidad, vendedor, observacion=f'Venta #{venta.pk}',
        )
        for lote, cantidad_tomada in consumo:
            VentaDetalleLote.objects.create(detalle=detalle, lote=lote, cantidad=cantidad_tomada)

        if receta_detalle:
            recetas_services.dispensar(
                receta_detalle, cantidad, vendedor, observacion=f'Venta #{venta.pk}',
                retirado_por=linea.get('retirado_por'),
            )

    # Puntos de fidelización: 1 punto por cada $100 vendidos (solo cliente identificado)
    if cliente:
        from apps.clientes.models import PuntosFidelizacion
        total_venta = sum(
            d.cantidad * d.precio_unitario for d in venta.detalles.all()
        )
        puntos_ganados = total_venta // 100
        if puntos_ganados > 0:
            PuntosFidelizacion.objects.create(
                cliente=cliente,
                puntos=puntos_ganados,
                motivo=f'Venta #{venta.pk}',
                venta_id=venta.pk,
            )

    return venta


@transaction.atomic
def anular_venta(venta, usuario, motivo):
    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if venta.estado == Venta.Estado.ANULADA:
        raise ValueError('Esta venta ya está anulada.')

    for detalle in venta.detalles.all():
        for consumo in detalle.lotes_consumidos.all():
            inventario_services.reintegrar_por_anulacion(
                consumo.lote, consumo.cantidad, usuario, observacion=f'Anulación de venta #{venta.pk}',
            )
        # El saldo de receta dispensada NO se revierte al anular: la receta
        # física ya quedó retenida y registrada en el libro de control,
        # independiente de si el producto vuelve físicamente a stock.

    if venta.cliente_id:
        movimientos = venta.cliente.puntos_fidelizacion
        abonados = movimientos.filter(venta_id=venta.pk, puntos__gt=0).aggregate(total=Sum('puntos'))['total']
        if abonados:
            movimientos.create(venta_id=venta.pk, puntos=-abonados, motivo=f'Anulación de venta #{venta.pk}')

    venta.estado = Venta.Estado.ANULADA
    venta.anulada_por = usuario
    venta.anulada_en = timezone.now()
    venta.motivo_anulacion = motivo
    venta.save(update_fields=['estado', 'anulada_por', 'anulada_en', 'motivo_anulacion'])
    return venta


@transaction.atomic
def emitir_documento(venta, tipo):
    if tipo == DocumentoTributario.Tipo.FACTURA and not venta.cliente_id:
        raise ValueError('No se puede facturar una venta sin cliente asociado.')

    ultimo = DocumentoTributario.objects.select_for_update().filter(tipo=tipo).order_by('-folio').first()
    siguiente_folio = (ultimo.folio + 1) if ultimo else 1

    return DocumentoTributario.objects.create(venta=venta, tipo=tipo, folio=siguiente_folio)
