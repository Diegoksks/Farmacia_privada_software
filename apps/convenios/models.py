from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.clientes.models import Cliente
from apps.productos.models import Categoria

PORCENTAJE_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class Convenio(models.Model):
    """Acuerdo con una Isapre o seguro complementario (RFP-08): define un
    descuento por defecto, afinable por categoría en ConvenioCobertura."""

    class Tipo(models.TextChoices):
        ISAPRE = 'ISAPRE', 'Isapre'
        SEGURO_COMPLEMENTARIO = 'SEGURO_COMPLEMENTARIO', 'Seguro complementario'

    nombre = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    descuento_porcentaje = models.PositiveIntegerField(
        default=0, validators=PORCENTAJE_VALIDATORS, help_text='Descuento por defecto si no hay cobertura específica por categoría',
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def descuento_para(self, producto):
        cobertura = self.coberturas.filter(categoria=producto.categoria).first()
        return cobertura.descuento_porcentaje if cobertura else self.descuento_porcentaje


class ConvenioCobertura(models.Model):
    """Override del % de descuento por categoría (ej: una Isapre cubre mejor
    medicamentos crónicos que insumos de aseo)."""

    convenio = models.ForeignKey(Convenio, on_delete=models.CASCADE, related_name='coberturas')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='+')
    descuento_porcentaje = models.PositiveIntegerField(validators=PORCENTAJE_VALIDATORS)

    class Meta:
        unique_together = [('convenio', 'categoria')]
        verbose_name = 'Cobertura por categoría'
        verbose_name_plural = 'Coberturas por categoría'

    def __str__(self):
        return f'{self.convenio} - {self.categoria}: {self.descuento_porcentaje}%'


class ClienteConvenio(models.Model):
    """Afiliación de un cliente a un convenio. Un cliente puede tener varios
    (Isapre + seguro complementario a la vez)."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='convenios')
    convenio = models.ForeignKey(Convenio, on_delete=models.PROTECT, related_name='afiliados')
    numero_afiliado = models.CharField(max_length=50, blank=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True, help_text='Vacío = indefinido')

    class Meta:
        unique_together = [('cliente', 'convenio')]
        verbose_name = 'Afiliación a convenio'
        verbose_name_plural = 'Afiliaciones a convenios'

    def __str__(self):
        return f'{self.cliente.nombre_completo} — {self.convenio}'

    def vigente(self, fecha):
        if fecha < self.vigente_desde:
            return False
        return self.vigente_hasta is None or fecha <= self.vigente_hasta
