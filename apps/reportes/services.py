from datetime import timedelta
import json

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.inventario.models import Lote
from apps.productos.models import Categoria, Producto
from apps.ventas.models import Venta, VentaDetalle


def _inicio_mes(fecha):
    return fecha.replace(day=1)


def _mes_siguiente(fecha):
    if fecha.month == 12:
        return fecha.replace(year=fecha.year + 1, month=1)
    return fecha.replace(month=fecha.month + 1)


def _total_vendido(**filtros_fecha):
    total = (
        VentaDetalle.objects
        .filter(venta__estado=Venta.Estado.COMPLETADA, **filtros_fecha)
        .aggregate(total=Sum(F('cantidad') * F('precio_unitario')))['total']
    )
    return total or 0


def ventas_por_dia(dias=30):
    """Retorna (labels, montos) de los últimos `dias` días.
    Incluye días con $0 y formatea seguro para Windows/Linux."""
    hoy = timezone.localdate()
    fechas = [hoy - timedelta(days=i) for i in range(dias - 1, -1, -1)]

    # Un solo query agrupado por fecha
    resultados = {
        row['venta__fecha__date']: row['total']
        for row in VentaDetalle.objects.filter(
            venta__estado=Venta.Estado.COMPLETADA,
            venta__fecha__date__gte=fechas[0],
            venta__fecha__date__lte=hoy,
        ).values('venta__fecha__date').annotate(
            total=Sum(F('cantidad') * F('precio_unitario'))
        )
    }
    labels = [f'{f.day} {f.strftime("%b")}' for f in fechas]
    montos = [int(resultados.get(f, 0)) for f in fechas]
    return labels, montos


def ventas_por_metodo_pago(inicio_mes, fin_mes):
    """Agrupa montos por método de pago para el gráfico de dona."""
    qs = (
        VentaDetalle.objects
        .filter(
            venta__estado=Venta.Estado.COMPLETADA,
            venta__fecha__date__gte=inicio_mes,
            venta__fecha__date__lt=fin_mes,
        )
        .values('venta__metodo_pago')
        .annotate(monto=Sum(F('cantidad') * F('precio_unitario')))
        .order_by('-monto')
    )
    etiquetas_pago = {
        'EFECTIVO': 'Efectivo', 'DEBITO': 'Débito',
        'CREDITO': 'Crédito', 'TRANSFERENCIA': 'Transferencia',
    }
    labels = [etiquetas_pago.get(row['venta__metodo_pago'], row['venta__metodo_pago']) for row in qs]
    montos  = [int(row['monto']) for row in qs]
    return labels, montos


def productos_mas_rentables(inicio_mes, fin_mes, top=10):
    """Productos ordenados por monto total vendido en el período."""
    return (
        VentaDetalle.objects
        .filter(
            venta__estado=Venta.Estado.COMPLETADA,
            venta__fecha__date__gte=inicio_mes,
            venta__fecha__date__lt=fin_mes,
        )
        .values('producto__nombre', 'producto__precio_venta')
        .annotate(
            cantidad_total=Sum('cantidad'),
            monto_total=Sum(F('cantidad') * F('precio_unitario')),
        )
        .order_by('-monto_total')[:top]
    )


def prediccion_demanda_simple():
    """Promedio de ventas por producto en los últimos 3 meses × 1.1."""
    hoy = timezone.localdate()
    hace_3_meses = _inicio_mes(hoy - timedelta(days=90))

    qs = (
        VentaDetalle.objects
        .filter(venta__estado=Venta.Estado.COMPLETADA, venta__fecha__date__gte=hace_3_meses)
        .values('producto__nombre', 'producto__stock_minimo')
        .annotate(total_vendido=Sum('cantidad'))
        .order_by('-total_vendido')[:15]
    )
    resultado = []
    for row in qs:
        promedio_mes = round(row['total_vendido'] / 3, 1)
        prediccion   = round(promedio_mes * 1.1, 1)
        resultado.append({
            'nombre':       row['producto__nombre'],
            'vendido_3m':   row['total_vendido'],
            'promedio_mes': promedio_mes,
            'prediccion':   prediccion,
            'stock_minimo': row['producto__stock_minimo'],
        })
    return resultado


def resumen_dashboard():
    """Todos los indicadores comerciales para el dashboard (RFP-11/12)."""
    hoy = timezone.localdate()
    inicio_mes_actual    = _inicio_mes(hoy)
    inicio_mes_siguiente = _mes_siguiente(inicio_mes_actual)
    inicio_mes_anterior  = _inicio_mes(inicio_mes_actual - timedelta(days=1))

    ventas_hoy          = _total_vendido(venta__fecha__date=hoy)
    ventas_mes_actual   = _total_vendido(
        venta__fecha__date__gte=inicio_mes_actual,
        venta__fecha__date__lt=inicio_mes_siguiente,
    )
    ventas_mes_anterior = _total_vendido(
        venta__fecha__date__gte=inicio_mes_anterior,
        venta__fecha__date__lt=inicio_mes_actual,
    )

    variacion_pct = None
    if ventas_mes_anterior:
        variacion_pct = round(
            (ventas_mes_actual - ventas_mes_anterior) / ventas_mes_anterior * 100, 1
        )

    detalles_mes = VentaDetalle.objects.filter(
        venta__estado=Venta.Estado.COMPLETADA,
        venta__fecha__date__gte=inicio_mes_actual,
        venta__fecha__date__lt=inicio_mes_siguiente,
    )

    top_productos = (
        detalles_mes.values('producto__nombre')
        .annotate(cantidad_total=Sum('cantidad'), monto_total=Sum(F('cantidad') * F('precio_unitario')))
        .order_by('-monto_total')[:5]
    )

    ventas_por_categoria = (
        detalles_mes.values('producto__categoria__nombre')
        .annotate(monto_total=Sum(F('cantidad') * F('precio_unitario')))
        .order_by('-monto_total')
    )

    stock_por_categoria = (
        Categoria.objects
        .annotate(
            unidades=Coalesce(Sum('productos__lotes__stocks__cantidad'), 0),
            productos_activos=Count('productos', filter=Q(productos__activo=True), distinct=True),
        )
        .order_by('nombre')
    )

    productos_stock_critico = (
        Producto.objects.filter(activo=True)
        .annotate(stock_actual=Coalesce(Sum('lotes__stocks__cantidad'), 0))
        .filter(stock_actual__lte=F('stock_minimo'))
        .order_by('stock_actual')
    )

    fecha_limite = hoy + timedelta(days=90)
    lotes_por_vencer = (
        Lote.objects
        .annotate(stock_actual=Coalesce(Sum('stocks__cantidad'), 0))
        .filter(fecha_vencimiento__lte=fecha_limite, stock_actual__gt=0)
        .select_related('producto')
        .order_by('fecha_vencimiento')
    )

    # Datos para Chart.js
    labels_30d, montos_30d = ventas_por_dia(30)
    labels_7d,  montos_7d  = ventas_por_dia(7)
    labels_pago, montos_pago = ventas_por_metodo_pago(inicio_mes_actual, inicio_mes_siguiente)

    rentables  = list(productos_mas_rentables(inicio_mes_actual, inicio_mes_siguiente))
    prediccion = prediccion_demanda_simple()

    return {
        'ventas_hoy':              ventas_hoy,
        'ventas_mes_actual':       ventas_mes_actual,
        'ventas_mes_anterior':     ventas_mes_anterior,
        'variacion_pct':           variacion_pct,
        'top_productos':           top_productos,
        'ventas_por_categoria':    ventas_por_categoria,
        'stock_por_categoria':     stock_por_categoria,
        'productos_stock_critico': productos_stock_critico,
        'lotes_por_vencer':        lotes_por_vencer,
        # Chart.js JSON
        'chart_30d_labels':  json.dumps(labels_30d),
        'chart_30d_montos':  json.dumps(montos_30d),
        'chart_7d_labels':   json.dumps(labels_7d),
        'chart_7d_montos':   json.dumps(montos_7d),
        'chart_pago_labels': json.dumps(labels_pago),
        'chart_pago_montos': json.dumps(montos_pago),
        'productos_rentables': rentables,
        'prediccion_demanda':  prediccion,
    }


def dataset_ventas(desde, hasta):
    """Líneas de venta completadas entre dos fechas (inclusive)."""
    return (
        VentaDetalle.objects
        .filter(
            venta__estado=Venta.Estado.COMPLETADA,
            venta__fecha__date__gte=desde,
            venta__fecha__date__lte=hasta,
        )
        .select_related('venta', 'venta__cliente', 'producto')
        .order_by('venta__fecha')
    )


def dataset_inventario():
    """Stock actual por producto activo, para el reporte exportable de
    inventario (RFP-12)."""
    return (
        Producto.objects.filter(activo=True)
        .annotate(stock_actual=Coalesce(Sum('lotes__stocks__cantidad'), 0))
        .select_related('categoria')
        .order_by('nombre')
    )


