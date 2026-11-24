import datetime
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import F

from apps.recetas.models import RecetaDetalle

class Command(BaseCommand):
    help = 'Envía recordatorios automáticos a pacientes crónicos con recetas con saldo'

    def handle(self, *args, **kwargs):
        hoy = timezone.localdate()
        # Buscar detalles de receta donde haya saldo y la receta siga vigente
        detalles_pendientes = RecetaDetalle.objects.filter(
            cantidad_dispensada__lt=F('cantidad_prescrita'),
            receta__fecha_emision__lte=hoy,
            receta__fecha_vencimiento__gte=hoy,
            receta__cliente__email__isnull=False
        ).exclude(receta__cliente__email='').select_related('receta__cliente', 'producto')

        enviados = 0
        for detalle in detalles_pendientes:
            cliente = detalle.receta.cliente
            if not cliente.email:
                continue

            asunto = f'Farmacia Privada: Tienes un saldo disponible para retirar de {detalle.producto.nombre}'
            mensaje = (
                f'Hola {cliente.nombres},\n\n'
                f'Te recordamos que tienes un saldo pendiente de retirar en tu receta '
                f'(Folio: {detalle.receta.folio_documento}).\n\n'
                f'Producto: {detalle.producto.nombre}\n'
                f'Saldo disponible: {detalle.saldo}\n\n'
                f'Puedes acercarte a nuestra sucursal para realizar el retiro de tu medicamento.\n\n'
                f'Saludos,\nEl equipo de Farmacia Privada.'
            )

            try:
                send_mail(
                    asunto,
                    mensaje,
                    'no-reply@farmaciaprivada.cl',
                    [cliente.email],
                    fail_silently=False,
                )
                enviados += 1
                self.stdout.write(self.style.SUCCESS(f'Recordatorio enviado a {cliente.email} para {detalle.producto.nombre}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error enviando a {cliente.email}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'Proceso completado. {enviados} correos enviados.'))
