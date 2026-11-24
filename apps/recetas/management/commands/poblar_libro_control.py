from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.clientes.models import Cliente
from apps.productos.models import Producto
from apps.recetas.models import Receta, RecetaDetalle, DispensacionReceta, LibroControl
from apps.usuarios.models import Usuario


class Command(BaseCommand):
    help = 'Puebla el Libro de Control Digital con entradas realistas de estupefacientes y psicotrópicos'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Poblando Libro de Control Digital (Cumplimiento ISP) ==='))

        admin = Usuario.objects.filter(is_superuser=True).first() or Usuario.objects.first()
        clientes = list(Cliente.objects.filter(activo=True))
        if not clientes:
            self.stdout.write(self.style.ERROR('No hay clientes registrados.'))
            return

        prods = {
            'clonazepam': Producto.objects.filter(nombre__icontains='Clonazepam').first(),
            'alprazolam': Producto.objects.filter(nombre__icontains='Alprazolam').first(),
            'morfina': Producto.objects.filter(nombre__icontains='Morfina').first(),
            'warfarina': Producto.objects.filter(nombre__icontains='Warfarina').first(),
        }

        # Asegurar que los productos requeridos existan con nivel_control = RECETA_RETENIDA
        if not prods['clonazepam'] or not prods['alprazolam']:
            self.stdout.write(self.style.ERROR('Faltan productos de receta retenida en catálogo.'))
            return

        ahora = timezone.now()

        # Datos realistas para el libro de control
        entradas_data = [
            {
                'dias_atras': 12,
                'horas_atras': 3,
                'medico_rut': '12876543-2',
                'medico_nombre': 'Dr. Patricio Valenzuela Alarcón',
                'cliente_idx': 0,
                'producto': prods['clonazepam'],
                'posologia': '1 comprimido antes de dormir (vía oral)',
                'prescrita': 30,
                'cantidad': 1,
                'folio': 'ISP-2026-0891',
                'tercero': None,
                'obs': 'Primera entrega de tratamiento para insomnio crónico severo',
            },
            {
                'dias_atras': 9,
                'horas_atras': 5,
                'medico_rut': '14321987-K',
                'medico_nombre': 'Dra. Francisca Morales Silva (Psiquiatra)',
                'cliente_idx': 1 % len(clientes),
                'producto': prods['alprazolam'],
                'posologia': '0.5mg en caso de crisis de pánico (máximo 2 diarios)',
                'prescrita': 30,
                'cantidad': 2,
                'folio': 'ISP-2026-0914',
                'tercero': {
                    'nombre': 'Rodrigo Herrera Morales',
                    'rut': '18765432-1',
                    'relacion': 'Hijo del paciente',
                },
                'obs': 'Retira hijo presentando poder simple y carnet del paciente',
            },
            {
                'dias_atras': 7,
                'horas_atras': 2,
                'medico_rut': '10456789-3',
                'medico_nombre': 'Dr. Alejandro Guzmán Toro (Paliativista)',
                'cliente_idx': 2 % len(clientes),
                'producto': prods['morfina'] or prods['clonazepam'],
                'posologia': '1 ampolla subcutánea SOS dolor oncológico severo',
                'prescrita': 10,
                'cantidad': 5,
                'folio': 'ISP-2026-0932',
                'tercero': {
                    'nombre': 'Rosa Cifuentes Gómez',
                    'rut': '13210987-4',
                    'relacion': 'Cuidadora formal',
                },
                'obs': 'Programa de cuidados paliativos y alivio del dolor crónico',
            },
            {
                'dias_atras': 5,
                'horas_atras': 6,
                'medico_rut': '15654321-8',
                'medico_nombre': 'Dra. Claudia Herrera Parra',
                'cliente_idx': 3 % len(clientes),
                'producto': prods['warfarina'] or prods['alprazolam'],
                'posologia': '1 comprimido diario según control INR mensual',
                'prescrita': 30,
                'cantidad': 1,
                'folio': 'ISP-2026-0955',
                'tercero': None,
                'obs': 'Retira titular con carnet de identidad vigente',
            },
            {
                'dias_atras': 3,
                'horas_atras': 4,
                'medico_rut': '12876543-2',
                'medico_nombre': 'Dr. Patricio Valenzuela Alarcón',
                'cliente_idx': 4 % len(clientes),
                'producto': prods['clonazepam'],
                'posologia': 'Medio comprimido cada 12 horas',
                'prescrita': 30,
                'cantidad': 1,
                'folio': 'ISP-2026-0980',
                'tercero': {
                    'nombre': 'Lorena Soto Valdés',
                    'rut': '16543210-9',
                    'relacion': 'Cónyuge',
                },
                'obs': 'Retira cónyuge por imposibilidad de traslado del paciente',
            },
            {
                'dias_atras': 2,
                'horas_atras': 1,
                'medico_rut': '14321987-K',
                'medico_nombre': 'Dra. Francisca Morales Silva (Psiquiatra)',
                'cliente_idx': 0,
                'producto': prods['alprazolam'],
                'posologia': '1 comprimido nocturno según necesidad',
                'prescrita': 30,
                'cantidad': 1,
                'folio': 'ISP-2026-1002',
                'tercero': None,
                'obs': 'Entrega conforme de receta retenida bajo control',
            },
            {
                'dias_atras': 0,
                'horas_atras': 2,
                'medico_rut': '10456789-3',
                'medico_nombre': 'Dr. Alejandro Guzmán Toro (Paliativista)',
                'cliente_idx': 1 % len(clientes),
                'producto': prods['morfina'] or prods['clonazepam'],
                'posologia': '1 ampolla subcutánea cada 8 horas',
                'prescrita': 10,
                'cantidad': 3,
                'folio': 'ISP-2026-1025',
                'tercero': {
                    'nombre': 'Rodrigo Herrera Morales',
                    'rut': '18765432-1',
                    'relacion': 'Hijo del paciente',
                },
                'obs': 'Dispensación urgente ambulatoria para manejo de dolor',
            },
        ]

        creadas = 0
        for item in entradas_data:
            cliente = clientes[item['cliente_idx']]
            fecha_receta = (ahora - timedelta(days=item['dias_atras'] + 5)).date()
            fecha_vencimiento = fecha_receta + timedelta(days=30)
            fecha_disp = ahora - timedelta(days=item['dias_atras'], hours=item['horas_atras'])

            # Crear o recuperar Receta
            receta, _ = Receta.objects.get_or_create(
                folio=item['folio'],
                defaults=dict(
                    cliente=cliente,
                    medico_rut=item['medico_rut'],
                    medico_nombre=item['medico_nombre'],
                    tipo=Receta.Tipo.FISICA,
                    fecha_emision=fecha_receta,
                    fecha_vencimiento=fecha_vencimiento,
                    creado_por=admin,
                )
            )

            # Crear o recuperar Detalle
            detalle, _ = RecetaDetalle.objects.get_or_create(
                receta=receta,
                producto=item['producto'],
                defaults=dict(
                    posologia=item['posologia'],
                    cantidad_prescrita=item['prescrita'],
                    cantidad_dispensada=item['cantidad'],
                )
            )

            # Crear Dispensacion en el Libro de Control
            tercero = item['tercero'] or {}
            disp = DispensacionReceta.objects.create(
                detalle=detalle,
                cantidad=item['cantidad'],
                usuario=admin,
                observacion=item['obs'],
                retirado_por_nombre=tercero.get('nombre', ''),
                retirado_por_rut=tercero.get('rut', ''),
                retirado_por_relacion=tercero.get('relacion', ''),
            )
            # Ajustar fecha exacta al pasado para cronología histórica creíble
            DispensacionReceta.objects.filter(pk=disp.pk).update(fecha=fecha_disp)
            creadas += 1

        total_libro = LibroControl.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'Se crearon exitosamente {creadas} entradas controladas. Total en Libro de Control: {total_libro}'
        ))
