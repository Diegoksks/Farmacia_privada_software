from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.comun.validators import normalizar_rut, validar_rut
from apps.productos.models import Producto


class Receta(models.Model):
    """Encabezado de una receta médica (RFP-09): quién la emitió, a quién, y
    su vigencia. Los medicamentos prescritos viven en RecetaDetalle."""

    class Tipo(models.TextChoices):
        FISICA = 'FISICA', 'Física'
        DIGITAL = 'DIGITAL', 'Digital'

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='recetas')
    medico_rut = models.CharField(max_length=12, validators=[validar_rut], verbose_name='RUT del médico')
    medico_nombre = models.CharField(max_length=150, verbose_name='Nombre del médico')
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    folio = models.CharField(max_length=30, blank=True, unique=True, null=True, help_text='Folio del talonario, si aplica')
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recetas_registradas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_emision']

    def __str__(self):
        return f'Receta #{self.pk} - {self.cliente.nombre_completo} ({self.fecha_emision})'

    def clean(self):
        super().clean()
        if self.fecha_vencimiento and self.fecha_emision and self.fecha_vencimiento < self.fecha_emision:
            raise ValidationError({'fecha_vencimiento': 'La fecha de vencimiento no puede ser anterior a la de emisión.'})

    @property
    def esta_vigente(self):
        hoy = timezone.localdate()
        return self.fecha_emision <= hoy <= self.fecha_vencimiento


class RecetaDetalle(models.Model):
    """Un medicamento prescrito dentro de una receta, con su saldo restante
    para tratamientos crónicos (cantidad_prescrita - cantidad_dispensada)."""

    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='+')
    posologia = models.CharField(max_length=255, blank=True, help_text='Dosis e indicaciones, ej: 1 comp. cada 8 horas')
    cantidad_prescrita = models.PositiveIntegerField()
    cantidad_dispensada = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Línea de receta'
        verbose_name_plural = 'Líneas de receta'

    def __str__(self):
        return f'{self.producto.nombre} x{self.cantidad_prescrita} ({self.receta})'

    def clean(self):
        super().clean()
        if self.producto_id and self.receta_id and not self.producto.requiere_receta:
            raise ValidationError({'producto': 'Este producto es de venta libre, no necesita receta.'})

    @property
    def saldo(self):
        return self.cantidad_prescrita - self.cantidad_dispensada

    @property
    def con_saldo(self):
        return self.saldo > 0

    @property
    def requiere_retencion(self):
        return self.producto.es_medicamento_controlado


class DispensacionReceta(models.Model):
    """Ledger inmutable de cada entrega parcial contra una receta. Lo usará
    ventas más adelante para descontar saldo al dispensar en mostrador."""

    detalle = models.ForeignKey(RecetaDetalle, on_delete=models.PROTECT, related_name='dispensaciones')
    cantidad = models.PositiveIntegerField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispensaciones_receta',
    )
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.CharField(max_length=255, blank=True)
    # Trazabilidad de la entrega: quién se llevó físicamente el medicamento.
    # Vacío significa que retiró el propio paciente de la receta.
    retirado_por_nombre = models.CharField(max_length=150, blank=True, verbose_name='Retirado por')
    retirado_por_rut = models.CharField(max_length=12, blank=True, validators=[validar_rut], verbose_name='RUT de quien retira')
    retirado_por_relacion = models.CharField(
        max_length=60, blank=True, verbose_name='Relación con el paciente', help_text='Ej: padre, madre, cuidador',
    )

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Dispensación de receta'
        verbose_name_plural = 'Dispensaciones de receta'

    def __str__(self):
        return f'{self.detalle.producto.nombre} x{self.cantidad} - {self.fecha:%d-%m-%Y}'

    def clean(self):
        super().clean()
        if self.retirado_por_rut and not self.retirado_por_nombre:
            raise ValidationError({'retirado_por_nombre': 'Indica el nombre de quien retira.'})

    def save(self, *args, **kwargs):
        if self.retirado_por_rut:
            self.retirado_por_rut = normalizar_rut(self.retirado_por_rut)
        super().save(*args, **kwargs)

    @property
    def retiro_por_tercero(self):
        return bool(self.retirado_por_nombre)

    @property
    def retirado_por(self):
        """Quién retiró, para mostrar en el libro de control y la trazabilidad."""
        if not self.retiro_por_tercero:
            return f'{self.detalle.receta.cliente.nombre_completo} (paciente)'
        partes = [self.retirado_por_nombre]
        if self.retirado_por_rut:
            partes.append(self.retirado_por_rut)
        if self.retirado_por_relacion:
            partes.append(self.retirado_por_relacion)
        return ' — '.join(partes)


class LibroControlManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            detalle__producto__nivel_control=Producto.NivelControl.RECETA_RETENIDA,
        )


class LibroControl(DispensacionReceta):
    """Vista de solo lectura sobre DispensacionReceta, filtrada a medicamentos
    de receta retenida: es el libro digital de control que exige el
    reglamento del ISP para estupefacientes y psicotrópicos (RFP-10)."""

    objects = LibroControlManager()

    class Meta:
        proxy = True
        verbose_name = 'Entrada del libro de control'
        verbose_name_plural = 'Libro de control (estupefacientes/psicotrópicos)'
