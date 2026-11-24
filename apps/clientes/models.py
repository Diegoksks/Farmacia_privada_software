from django.db import models

from apps.comun.validators import normalizar_rut, validar_rut


class Cliente(models.Model):
    """Cliente/Paciente que compra o retira productos. No es un Usuario del
    sistema (no inicia sesión); recetas y convenios lo referencian por RUT."""

    rut = models.CharField(max_length=12, unique=True, validators=[validar_rut])
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['apellidos', 'nombres']

    def __str__(self):
        return f'{self.nombre_completo} ({self.rut})'

    @property
    def nombre_completo(self):
        return f'{self.nombres} {self.apellidos}'

    def save(self, *args, **kwargs):
        if self.rut:
            self.rut = normalizar_rut(self.rut)
        super().save(*args, **kwargs)

    @property
    def saldo_puntos(self):
        """Puntos acumulados disponibles (positivos = acumula, negativos = canje)."""
        return self.puntos_fidelizacion.aggregate(
            total=models.Sum('puntos')
        )['total'] or 0


class PuntosFidelizacion(models.Model):
    """Ledger de puntos por fidelización del cliente.
    1 punto por cada $100 comprados. Los canjes restan puntos (puntos < 0).
    """
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name='puntos_fidelizacion',
    )
    puntos = models.IntegerField(help_text='Positivo=acumulación, negativo=canje')
    motivo = models.CharField(max_length=200)
    fecha  = models.DateTimeField(auto_now_add=True)
    # Referencia opcional a la venta que generó los puntos
    venta_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Movimiento de puntos'
        verbose_name_plural = 'Historial de puntos'

    def __str__(self):
        signo = '+' if self.puntos >= 0 else ''
        return f'{self.cliente.nombre_completo}: {signo}{self.puntos} pts — {self.motivo}'
