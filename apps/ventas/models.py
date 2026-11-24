from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.clientes.models import Cliente
from apps.convenios.models import Convenio
from apps.inventario.models import Lote
from apps.productos.models import Producto
from apps.recetas.models import RecetaDetalle


class Caja(models.Model):
    """Turno de caja de un vendedor: apertura con un monto inicial, cierre
    con lo declarado físicamente vs. lo que el sistema calculó (RFP-06,
    control de caja diaria). La diferencia es el descuadre."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cajas')
    monto_apertura = models.PositiveIntegerField()
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    monto_cierre_declarado = models.PositiveIntegerField(null=True, blank=True)
    monto_cierre_sistema = models.PositiveIntegerField(null=True, blank=True)
    diferencia = models.IntegerField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_apertura']

    def __str__(self):
        estado = 'abierta' if self.esta_abierta else 'cerrada'
        return f'Caja #{self.pk} - {self.usuario} ({estado})'

    @property
    def esta_abierta(self):
        return self.fecha_cierre is None

    def calcular_monto_sistema(self):
        total_efectivo = self.ventas.filter(
            estado=Venta.Estado.COMPLETADA, metodo_pago=Venta.MetodoPago.EFECTIVO,
        ).aggregate(
            total=models.Sum(models.F('detalles__cantidad') * models.F('detalles__precio_unitario')),
        )['total'] or 0
        return self.monto_apertura + total_efectivo


class Venta(models.Model):
    """Encabezado de una venta (RFP-06). Cada línea descuenta stock de
    vitrina por FEFO y, si el producto requiere receta, saldo de receta."""

    class MetodoPago(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        DEBITO = 'DEBITO', 'Débito'
        CREDITO = 'CREDITO', 'Crédito'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia'

    class Estado(models.TextChoices):
        COMPLETADA = 'COMPLETADA', 'Completada'
        ANULADA = 'ANULADA', 'Anulada'

    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name='ventas')
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name='ventas')
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ventas_realizadas')
    metodo_pago = models.CharField(max_length=15, choices=MetodoPago.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.COMPLETADA)
    fecha = models.DateTimeField(auto_now_add=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_anuladas',
    )
    anulada_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'Venta #{self.pk} - {self.get_estado_display()}'

    @property
    def total(self):
        return sum(detalle.subtotal for detalle in self.detalles.all())


class VentaDetalle(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='+')
    cantidad = models.PositiveIntegerField()
    precio_lista = models.PositiveIntegerField(help_text='Precio de catálogo antes de descuentos, en CLP')
    precio_unitario = models.PositiveIntegerField(help_text='Precio final cobrado (con descuento de convenio si aplica), en CLP')
    convenio = models.ForeignKey(
        Convenio, on_delete=models.PROTECT, null=True, blank=True, related_name='+',
        help_text='Convenio aplicado para el descuento, si corresponde',
    )
    receta_detalle = models.ForeignKey(
        RecetaDetalle, on_delete=models.PROTECT, null=True, blank=True, related_name='ventas_asociadas',
    )

    def __str__(self):
        return f'{self.producto.nombre} x{self.cantidad}'

    class Meta:
        verbose_name = 'Línea de venta'
        verbose_name_plural = 'Líneas de venta'

    def clean(self):
        super().clean()
        if self.producto_id and self.producto.requiere_receta and not self.receta_detalle_id:
            raise ValidationError({'receta_detalle': 'Este producto requiere una receta con saldo disponible.'})

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class VentaDetalleLote(models.Model):
    """De qué lote(s) exactos salió cada línea (FEFO puede repartir una
    misma línea entre varios lotes). Se usa para reintegrar stock si la
    venta se anula."""

    detalle = models.ForeignKey(VentaDetalle, on_delete=models.CASCADE, related_name='lotes_consumidos')
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()

    class Meta:
        verbose_name = 'Lote consumido en venta'
        verbose_name_plural = 'Lotes consumidos en venta'

    def __str__(self):
        return f'{self.lote} x{self.cantidad}'


class DocumentoTributario(models.Model):
    """Boleta o factura SIMULADA (RFP-07): no hay integración real con el
    SII, solo folio correlativo y tipo, propio de un proyecto académico."""

    class Tipo(models.TextChoices):
        BOLETA = 'BOLETA', 'Boleta'
        FACTURA = 'FACTURA', 'Factura'

    venta = models.OneToOneField(Venta, on_delete=models.PROTECT, related_name='documento_tributario')
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    folio = models.PositiveIntegerField()
    fecha_emision = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('tipo', 'folio')]
        ordering = ['-fecha_emision']
        verbose_name = 'Documento tributario'
        verbose_name_plural = 'Documentos tributarios'

    def __str__(self):
        return f'{self.get_tipo_display()} N° {self.folio}'

    def clean(self):
        super().clean()
        if self.tipo == self.Tipo.FACTURA and self.venta_id and not self.venta.cliente_id:
            raise ValidationError('No se puede facturar una venta sin cliente asociado.')
