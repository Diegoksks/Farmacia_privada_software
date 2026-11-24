from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.productos.models import Producto


class Ubicacion(models.TextChoices):
    BODEGA = 'BODEGA', 'Bodega'
    VITRINA = 'VITRINA', 'Vitrina'


class Lote(models.Model):
    """Lote de un producto con su fecha de vencimiento (RFP-05). El stock por
    ubicación vive en Stock; este modelo es solo la identidad del lote."""

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='lotes')
    numero_lote = models.CharField(max_length=50)
    fecha_vencimiento = models.DateField()
    fecha_ingreso = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('producto', 'numero_lote')]
        ordering = ['fecha_vencimiento']

    def __str__(self):
        return f'{self.producto.nombre} - Lote {self.numero_lote}'

    @property
    def dias_para_vencer(self):
        return (self.fecha_vencimiento - timezone.localdate()).days

    def esta_por_vencer(self, dias=90):
        return self.dias_para_vencer <= dias

    @property
    def stock_total(self):
        return self.stocks.aggregate(total=models.Sum('cantidad'))['total'] or 0


class Stock(models.Model):
    """Cantidad actual de un lote en una ubicación (bodega o vitrina). Solo se
    modifica a través de apps.inventario.services para quedar siempre
    respaldado por un MovimientoStock."""

    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name='stocks')
    ubicacion = models.CharField(max_length=10, choices=Ubicacion.choices)
    cantidad = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('lote', 'ubicacion')]
        verbose_name_plural = 'Stock'

    def __str__(self):
        return f'{self.lote} @ {self.get_ubicacion_display()}: {self.cantidad}'


class MovimientoStock(models.Model):
    """Ledger inmutable de cada cambio de stock, para trazabilidad y auditoría
    (quién movió qué, cuándo y por qué). No se edita ni se borra."""

    class Tipo(models.TextChoices):
        INGRESO_COMPRA = 'INGRESO_COMPRA', 'Ingreso por compra'
        TRASPASO = 'TRASPASO', 'Traspaso bodega → vitrina'
        AJUSTE_POSITIVO = 'AJUSTE_POSITIVO', 'Ajuste positivo'
        AJUSTE_NEGATIVO = 'AJUSTE_NEGATIVO', 'Ajuste negativo'
        SALIDA_VENTA = 'SALIDA_VENTA', 'Salida por venta'
        DEVOLUCION_ANULACION = 'DEVOLUCION_ANULACION', 'Devolución por anulación de venta'

    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    ubicacion_origen = models.CharField(max_length=10, choices=Ubicacion.choices, null=True, blank=True)
    ubicacion_destino = models.CharField(max_length=10, choices=Ubicacion.choices, null=True, blank=True)
    cantidad = models.PositiveIntegerField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_stock',
    )
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Movimiento de stock'
        verbose_name_plural = 'Movimientos de stock'

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.lote} ({self.cantidad})'


class Proveedor(models.Model):
    """Proveedor de insumos y medicamentos para la clínica/farmacia."""

    nombre = models.CharField(max_length=150, unique=True, verbose_name='Razón Social / Nombre')
    rut = models.CharField(max_length=20, blank=True, verbose_name='RUT')
    giro = models.CharField(max_length=150, blank=True, verbose_name='Giro comercial')
    contacto_nombre = models.CharField(max_length=100, blank=True, verbose_name='Nombre de Contacto')
    telefono = models.CharField(max_length=30, blank=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Correo Electrónico')
    direccion = models.CharField(max_length=255, blank=True, verbose_name='Dirección')
    ciudad = models.CharField(max_length=100, blank=True, default='Santiago', verbose_name='Ciudad')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    notas = models.TextField(blank=True, verbose_name='Notas / Observaciones')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'

    def __str__(self):
        if self.rut:
            return f'{self.nombre} ({self.rut})'
        return self.nombre


class OrdenCompra(models.Model):
    """Orden de compra a proveedor (RFP-04). Al marcarse RECIBIDA genera los
    Lote/Stock/MovimientoStock correspondientes, siempre ingresando a bodega."""

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        RECIBIDA = 'RECIBIDA', 'Recibida'
        CANCELADA = 'CANCELADA', 'Cancelada'

    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT, related_name='ordenes_compra', verbose_name='Proveedor'
    )
    numero_factura = models.CharField(
        max_length=50, blank=True, verbose_name='N° Factura / Guía Despacho',
        help_text='Número de documento tributario entregado por el proveedor'
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_compra_creadas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    recibido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Orden de compra'
        verbose_name_plural = 'Órdenes de compra'

    def __str__(self):
        prov_nombre = self.proveedor.nombre if self.proveedor else 'Sin proveedor'
        return f'OC #{self.pk} - {prov_nombre} ({self.get_estado_display()})'

    @property
    def total_estimado(self):
        return sum(d.cantidad * d.precio_unitario for d in self.detalles.all())


class OrdenCompraDetalle(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    numero_lote = models.CharField(
        max_length=50, blank=True, default='', verbose_name='N° de Lote',
        help_text='Entregado por el proveedor al recepcionar'
    )
    fecha_vencimiento = models.DateField(
        null=True, blank=True, verbose_name='Fecha de Vencimiento',
        help_text='Fecha de vencimiento informada por el proveedor'
    )
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.PositiveIntegerField(help_text='Costo de compra por unidad, en CLP')

    class Meta:
        verbose_name = 'Línea de orden de compra'
        verbose_name_plural = 'Líneas de orden de compra'

    def __str__(self):
        if self.numero_lote:
            return f'{self.producto.nombre} x{self.cantidad} (lote {self.numero_lote})'
        return f'{self.producto.nombre} x{self.cantidad}'

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

