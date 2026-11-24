from django.core.validators import RegexValidator
from django.db import models

validar_codigo_barras = RegexValidator(r'^\d{6,20}$', 'El código de barras debe contener solo números (6 a 20 dígitos).')


class Categoria(models.Model):
    """Agrupa productos para indicadores de dashboard/reportes por categoría (RFP-11/12)."""

    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """Catálogo de medicamentos e insumos (RFP-03). No lleva stock: eso vive en
    inventario, que referencia este catálogo por producto y lote."""

    class Tipo(models.TextChoices):
        MEDICAMENTO = 'MEDICAMENTO', 'Medicamento'
        INSUMO = 'INSUMO', 'Insumo'

    class NivelControl(models.TextChoices):
        VENTA_LIBRE = 'VENTA_LIBRE', 'Venta libre'
        RECETA_SIMPLE = 'RECETA_SIMPLE', 'Receta simple'
        RECETA_RETENIDA = 'RECETA_RETENIDA', 'Receta retenida'

    class CategoriaRegulatoria(models.TextChoices):
        NINGUNA = 'NINGUNA', 'Ninguna'
        ESTUPEFACIENTE = 'ESTUPEFACIENTE', 'Estupefaciente'
        PSICOTROPICO = 'PSICOTROPICO', 'Psicotrópico'

    nombre = models.CharField(max_length=150)
    principio_activo = models.CharField(max_length=150, blank=True)
    laboratorio = models.CharField(max_length=100, blank=True)
    presentacion = models.CharField(max_length=150, blank=True, help_text='Ej: Caja x 30 comprimidos recubiertos')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    nivel_control = models.CharField(max_length=20, choices=NivelControl.choices)
    categoria_regulatoria = models.CharField(
        max_length=20, choices=CategoriaRegulatoria.choices, default=CategoriaRegulatoria.NINGUNA,
        help_text='Solo aplica a productos de receta retenida (reglamento ISP)',
    )
    codigo_barras = models.CharField(max_length=20, unique=True, validators=[validar_codigo_barras])
    precio_venta = models.PositiveIntegerField(help_text='Precio en pesos chilenos (CLP), sin descuentos de convenio')
    stock_minimo = models.PositiveIntegerField(default=10, help_text='Umbral bajo el cual se considera stock crítico')
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def requiere_receta(self):
        return self.nivel_control != self.NivelControl.VENTA_LIBRE

    @property
    def es_medicamento_controlado(self):
        return self.nivel_control == self.NivelControl.RECETA_RETENIDA
