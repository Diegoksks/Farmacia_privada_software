# Generated manually to handle data migration from CharField to ForeignKey
import django.db.models.deletion
from django.db import migrations, models


def poblar_proveedores(apps, schema_editor):
    Proveedor = apps.get_model('inventario', 'Proveedor')
    OrdenCompra = apps.get_model('inventario', 'OrdenCompra')

    proveedores_data = {
        'Distribuidora Pharmex Ltda.': {
            'rut': '76.845.120-3',
            'giro': 'Distribuidora Farmacéutica e Insumos Médicos',
            'contacto_nombre': 'Rodrigo Morales',
            'telefono': '+56 2 2456 7890',
            'email': 'ventas@pharmex.cl',
            'direccion': 'Av. Andrés Bello 2711, Providencia',
            'ciudad': 'Santiago',
        },
        'Laboratorio Recalcine S.A.': {
            'rut': '91.234.567-8',
            'giro': 'Laboratorio Farmacéutico Nacional',
            'contacto_nombre': 'María José Soto',
            'telefono': '+56 2 2345 6789',
            'email': 'pedidos@recalcine.cl',
            'direccion': 'Av. Vicuña Mackenna 1020, Ñuñoa',
            'ciudad': 'Santiago',
        },
        'Roche Chile S.A.': {
            'rut': '80.123.456-7',
            'giro': 'Laboratorio Farmacéutico Internacional',
            'contacto_nombre': 'Alejandro Valenzuela',
            'telefono': '+56 2 2987 6543',
            'email': 'suministros@roche.cl',
            'direccion': 'Av. Vitacura 5250, Las Condes',
            'ciudad': 'Santiago',
        },
        'Mintlab S.A. lote antiguo': {
            'rut': '96.543.210-5',
            'giro': 'Laboratorio de Medicamentos Genéricos',
            'contacto_nombre': 'Camila Henríquez',
            'telefono': '+56 2 2876 5432',
            'email': 'contacto@mintlab.cl',
            'direccion': 'San Ignacio 100, Quilicura',
            'ciudad': 'Santiago',
        },
    }

    prov_cache = {}
    for nombre, datos in proveedores_data.items():
        prov, _ = Proveedor.objects.get_or_create(nombre=nombre, defaults=datos)
        prov_cache[nombre] = prov

    for oc in OrdenCompra.objects.all():
        nombre_str = getattr(oc, 'proveedor_old', None) or 'Distribuidora Pharmex Ltda.'
        if nombre_str not in prov_cache:
            prov, _ = Proveedor.objects.get_or_create(
                nombre=nombre_str,
                defaults={
                    'rut': '77.000.000-1',
                    'giro': 'Proveedor Farmacéutico',
                    'ciudad': 'Santiago',
                }
            )
            prov_cache[nombre_str] = prov
        oc.proveedor = prov_cache[nombre_str]
        oc.save(update_fields=['proveedor'])


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0005_alter_movimientostock_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Proveedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150, unique=True, verbose_name='Razón Social / Nombre')),
                ('rut', models.CharField(blank=True, max_length=20, verbose_name='RUT')),
                ('giro', models.CharField(blank=True, max_length=150, verbose_name='Giro comercial')),
                ('contacto_nombre', models.CharField(blank=True, max_length=100, verbose_name='Nombre de Contacto')),
                ('telefono', models.CharField(blank=True, max_length=30, verbose_name='Teléfono')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Correo Electrónico')),
                ('direccion', models.CharField(blank=True, max_length=255, verbose_name='Dirección')),
                ('ciudad', models.CharField(blank=True, default='Santiago', max_length=100, verbose_name='Ciudad')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('notas', models.TextField(blank=True, verbose_name='Notas / Observaciones')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Proveedor',
                'verbose_name_plural': 'Proveedores',
                'ordering': ['nombre'],
            },
        ),
        migrations.RenameField(
            model_name='ordencompra',
            old_name='proveedor',
            new_name='proveedor_old',
        ),
        migrations.AddField(
            model_name='ordencompra',
            name='proveedor',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='ordenes_compra',
                to='inventario.proveedor',
                verbose_name='Proveedor'
            ),
        ),
        migrations.RunPython(poblar_proveedores, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='ordencompra',
            name='proveedor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='ordenes_compra',
                to='inventario.proveedor',
                verbose_name='Proveedor'
            ),
        ),
        migrations.RemoveField(
            model_name='ordencompra',
            name='proveedor_old',
        ),
        migrations.AddField(
            model_name='ordencompra',
            name='numero_factura',
            field=models.CharField(
                blank=True,
                help_text='Número de documento tributario entregado por el proveedor',
                max_length=50,
                verbose_name='N° Factura / Guía Despacho'
            ),
        ),
        migrations.AddField(
            model_name='ordencompra',
            name='observaciones',
            field=models.TextField(blank=True, verbose_name='Observaciones'),
        ),
        migrations.AlterField(
            model_name='ordencompradetalle',
            name='numero_lote',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Entregado por el proveedor al recepcionar',
                max_length=50,
                verbose_name='N° de Lote'
            ),
        ),
        migrations.AlterField(
            model_name='ordencompradetalle',
            name='fecha_vencimiento',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Fecha de vencimiento informada por el proveedor',
                verbose_name='Fecha de Vencimiento'
            ),
        ),
    ]
