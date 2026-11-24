"""
Comando: enviar_alertas
Envía un email al administrador con un resumen de:
 - Productos en stock crítico
 - Lotes próximos a vencer (≤ 30 días)
 - Cajas con descuadre del día anterior

Uso:
    python manage.py enviar_alertas
"""
from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.inventario.models import Lote
from apps.productos.models import Producto
from apps.usuarios.models import Usuario
from apps.ventas.models import Caja


class Command(BaseCommand):
    help = 'Envía email de alertas al administrador (stock crítico, vencimientos, descuadres de caja)'

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)
        lineas = []

        # 1. Stock crítico
        criticos = (
            Producto.objects.filter(activo=True)
            .annotate(stock_actual=Coalesce(Sum('lotes__stocks__cantidad'), 0))
            .filter(stock_actual__lte=F('stock_minimo'))
            .order_by('stock_actual')
        )
        if criticos.exists():
            lineas.append('=== STOCK CRÍTICO ===')
            for p in criticos:
                lineas.append(f'  • {p.nombre}: stock={p.stock_actual} (mínimo={p.stock_minimo})')
            lineas.append('')

        # 2. Lotes próximos a vencer (≤ 30 días)
        por_vencer = (
            Lote.objects
            .annotate(stock_actual=Coalesce(Sum('stocks__cantidad'), 0))
            .filter(fecha_vencimiento__lte=hoy + timedelta(days=30), stock_actual__gt=0)
            .select_related('producto')
            .order_by('fecha_vencimiento')
        )
        if por_vencer.exists():
            lineas.append('=== LOTES POR VENCER (≤ 30 DÍAS) ===')
            for lote in por_vencer:
                dias = (lote.fecha_vencimiento - hoy).days
                lineas.append(
                    f'  • {lote.producto.nombre} — Lote {lote.numero_lote}: '
                    f'vence {lote.fecha_vencimiento.strftime("%d/%m/%Y")} ({dias} días)'
                )
            lineas.append('')

        # 3. Cajas cerradas ayer con descuadre > $500
        cajas_descuadre = (
            Caja.objects.filter(
                fecha_cierre__date=ayer,
                diferencia__isnull=False,
            ).exclude(diferencia=0)
        )
        descuadres = [c for c in cajas_descuadre if abs(c.diferencia) > 500]
        if descuadres:
            lineas.append('=== DESCUADRES DE CAJA (ayer) ===')
            for c in descuadres:
                lineas.append(
                    f'  • {c.usuario.get_full_name()}: '
                    f'diferencia ${c.diferencia} '
                    f'(declarado=${c.monto_cierre_declarado} | sistema=${c.monto_cierre_sistema})'
                )
            lineas.append('')

        if not lineas:
            self.stdout.write(self.style.SUCCESS('Sin alertas activas. No se envió email.'))
            return

        cuerpo = '\n'.join(lineas)
        cuerpo = f'Resumen de alertas Farmacia Privada — {hoy.strftime("%d/%m/%Y")}\n\n' + cuerpo

        # Enviar a todos los administradores con email
        admins = Usuario.objects.filter(rol=Usuario.Rol.ADMINISTRADOR, email__isnull=False).exclude(email='')
        emails = list(admins.values_list('email', flat=True))

        if emails:
            send_mail(
                subject=f'⚠ Alertas Farmacia Privada — {hoy.strftime("%d/%m/%Y")}',
                message=cuerpo,
                from_email=None,
                recipient_list=emails,
            )
            self.stdout.write(self.style.SUCCESS(f'Email enviado a: {", ".join(emails)}'))
        else:
            self.stdout.write(self.style.WARNING('No hay administradores con email configurado.'))

        self.stdout.write(cuerpo)
