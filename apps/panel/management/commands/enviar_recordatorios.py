"""
Comando: enviar_recordatorios
Notifica por email a los clientes cuyos detalles de receta tienen saldo > 0
y cuya receta vence en los próximos 7 días.

Uso:
    python manage.py enviar_recordatorios
"""
from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from apps.recetas.models import RecetaDetalle


class Command(BaseCommand):
    help = 'Envía recordatorios por email a clientes con recetas próximas a vencer'

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        limite = hoy + timedelta(days=7)

        # Detalles de receta con saldo y receta que vence en 7 días
        detalles = (
            RecetaDetalle.objects
            .filter(
                cantidad_dispensada__lt=F('cantidad_prescrita'),
                receta__fecha_vencimiento__gte=hoy,
                receta__fecha_vencimiento__lte=limite,
            )
            .select_related('receta', 'receta__cliente', 'producto')
            .order_by('receta__fecha_vencimiento')
        )

        if not detalles.exists():
            self.stdout.write(self.style.SUCCESS('Sin recetas por vencer en los próximos 7 días.'))
            return

        # Agrupar por cliente
        por_cliente = {}
        for det in detalles:
            cliente = det.receta.cliente
            if cliente.pk not in por_cliente:
                por_cliente[cliente.pk] = {'cliente': cliente, 'detalles': []}
            por_cliente[cliente.pk]['detalles'].append(det)

        enviados = 0
        for grupo in por_cliente.values():
            cliente = grupo['cliente']
            if not cliente.email:
                self.stdout.write(self.style.WARNING(
                    f'  Sin email: {cliente.nombre_completo} — omitido'
                ))
                continue

            lineas = [f'Estimado/a {cliente.nombre_completo},\n']
            lineas.append('Le informamos que las siguientes recetas médicas están próximas a vencer:\n')
            for det in grupo['detalles']:
                dias = (det.receta.fecha_vencimiento - hoy).days
                saldo = det.cantidad_prescrita - det.cantidad_dispensada
                lineas.append(
                    f'  • {det.producto.nombre}: saldo {saldo} unidades — '
                    f'receta vence el {det.receta.fecha_vencimiento.strftime("%d/%m/%Y")} ({dias} días)'
                )

            lineas.append('\nPuede acercarse a nuestra farmacia para retirar su medicamento antes del vencimiento.')
            lineas.append('\nEquipo Farmacia Privada')

            cuerpo = '\n'.join(lineas)
            send_mail(
                subject='Recordatorio: receta próxima a vencer — Farmacia Privada',
                message=cuerpo,
                from_email=None,
                recipient_list=[cliente.email],
            )
            enviados += 1
            self.stdout.write(f'  → Recordatorio enviado a {cliente.email}')

        self.stdout.write(self.style.SUCCESS(f'\n{enviados} recordatorio(s) enviado(s).'))
