"""
Comando de gestión: poblar_datos
Crea un conjunto completo de datos de demostración para la Farmacia Privada.

Uso:
    python manage.py poblar_datos
    python manage.py poblar_datos --limpiar
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.convenios.models import ClienteConvenio, Convenio, ConvenioCobertura
from apps.inventario import services as inv_services
from apps.inventario.models import Lote, MovimientoStock, OrdenCompra, OrdenCompraDetalle, Stock, Proveedor
from apps.productos.models import Categoria, Producto
from apps.recetas.models import Receta, RecetaDetalle
from apps.usuarios.models import Usuario
from apps.ventas import services as ventas_services
from apps.ventas.models import Caja, DocumentoTributario, Venta, VentaDetalle, VentaDetalleLote


class Command(BaseCommand):
    help = 'Puebla la base de datos con datos de demostracion para la Farmacia Privada'

    def add_arguments(self, parser):
        parser.add_argument('--limpiar', action='store_true', help='Elimina todos los datos antes de crear los nuevos')

    def handle(self, *args, **options):
        if options['limpiar']:
            self._limpiar()
        with transaction.atomic():
            self.stdout.write(self.style.MIGRATE_HEADING('\n=== POBLANDO DATOS DE DEMOSTRACION ===\n'))
            admin = self._crear_usuarios()
            categorias, productos = self._crear_catalogo()
            convenios = self._crear_convenios(categorias)
            clientes = self._crear_clientes(convenios)
            self._crear_inventario(admin, productos)
            self._crear_recetas(clientes, productos, admin)
            self._crear_ventas(admin, clientes, productos)
            from django.core.management import call_command
            call_command('poblar_libro_control')
            self.stdout.write(self.style.SUCCESS('\nDatos de demostracion creados exitosamente.\n'))

    def _limpiar(self):
        self.stdout.write(self.style.WARNING('Eliminando datos existentes...'))
        VentaDetalleLote.objects.all().delete()
        VentaDetalle.objects.all().delete()
        DocumentoTributario.objects.all().delete()
        Venta.objects.all().delete()
        Caja.objects.all().delete()
        RecetaDetalle.objects.all().delete()
        Receta.objects.all().delete()
        ClienteConvenio.objects.all().delete()
        Cliente.objects.all().delete()
        ConvenioCobertura.objects.all().delete()
        Convenio.objects.all().delete()
        MovimientoStock.objects.all().delete()
        Stock.objects.all().delete()
        OrdenCompraDetalle.objects.all().delete()
        OrdenCompra.objects.all().delete()
        Lote.objects.all().delete()
        Producto.objects.all().delete()
        Categoria.objects.all().delete()
        Usuario.objects.filter(username__in=['vendedor1','vendedor2','tecnico1','quimico1']).delete()
        self.stdout.write(self.style.SUCCESS('Listo.\n'))

    def _crear_usuarios(self):
        self.stdout.write('Creando usuarios...')
        admin, _ = Usuario.objects.get_or_create(username='admin', defaults=dict(
            email='admin@farmacia.cl', first_name='Admin', last_name='Sistema',
            rut='12345678-9', rol=Usuario.Rol.ADMINISTRADOR, is_superuser=True, is_staff=True))
        if not admin.has_usable_password():
            admin.set_password('admin1234'); admin.save()
        for data in [
            dict(username='vendedor1',email='vendedor1@farmacia.cl',first_name='Camila',last_name='Rojas',rut='11111111-1',rol=Usuario.Rol.VENDEDOR,pw='vendedor1234'),
            dict(username='vendedor2',email='vendedor2@farmacia.cl',first_name='Sebastian',last_name='Munoz',rut='22222222-2',rol=Usuario.Rol.VENDEDOR,pw='vendedor1234'),
            dict(username='tecnico1',email='tecnico1@farmacia.cl',first_name='Javiera',last_name='Lopez',rut='33333333-3',rol=Usuario.Rol.TECNICO_FARMACIA,pw='tecnico1234'),
            dict(username='quimico1',email='quimico1@farmacia.cl',first_name='Andres',last_name='Perez',rut='44444444-4',rol=Usuario.Rol.QUIMICO_FARMACEUTICO,pw='quimico1234'),
        ]:
            pw = data.pop('pw')
            u, created = Usuario.objects.get_or_create(username=data['username'], defaults=data)
            if created: u.set_password(pw); u.save()
        self.stdout.write(f'   {Usuario.objects.count()} usuarios')
        return admin

    def _crear_catalogo(self):
        self.stdout.write('Creando catalogo...')
        cats = {}
        for nombre, desc in [
            ('Analgesicos y antiinflamatorios','Paracetamol, ibuprofeno, ketoprofeno'),
            ('Antibioticos','Antimicrobianos de receta medica'),
            ('Cardiovascular','Antihipertensivos, anticoagulantes, estatinas'),
            ('Diabetes y metabolismo','Insulinas, metformina, hipoglucemiantes'),
            ('Salud mental','Ansioliticos, antidepresivos, antipsicóticos'),
            ('Insumos medicos','Gasas, jeringas, guantes, material de curacion'),
            ('Vitaminas y suplementos','Vitamina C, D, complejo B, calcio'),
            ('Dermatologia','Cremas, unguentos, tratamientos topicos'),
        ]:
            c,_=Categoria.objects.get_or_create(nombre=nombre,defaults={'descripcion':desc})
            cats[nombre]=c

        prods_data=[
            ('Paracetamol 500mg','Paracetamol','Pasteur','Caja x 20 comprimidos','Analgesicos y antiinflamatorios','MEDICAMENTO','VENTA_LIBRE','NINGUNA','7801234000010',2500,50),
            ('Ibuprofeno 400mg','Ibuprofeno','Mintlab','Caja x 20 comprimidos','Analgesicos y antiinflamatorios','MEDICAMENTO','VENTA_LIBRE','NINGUNA','7801234000027',3200,30),
            ('Ketoprofeno 50mg','Ketoprofeno','Saval','Ampolla 2ml c/5','Analgesicos y antiinflamatorios','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000034',8900,20),
            ('Diclofenaco 75mg','Diclofenaco sodico','Bago','Caja x 30 comprimidos','Analgesicos y antiinflamatorios','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000041',5400,25),
            ('Amoxicilina 500mg','Amoxicilina','Recalcine','Caja x 21 capsulas','Antibioticos','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000058',6800,30),
            ('Azitromicina 500mg','Azitromicina','Mintlab','Caja x 3 comprimidos','Antibioticos','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000065',9200,20),
            ('Ciprofloxacino 500mg','Ciprofloxacino','Pasteur','Caja x 10 comprimidos','Antibioticos','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000072',7600,15),
            ('Losartan 50mg','Losartan potasico','Mintlab','Caja x 30 comprimidos','Cardiovascular','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000089',4200,40),
            ('Atorvastatina 20mg','Atorvastatina','Pfizer','Caja x 30 comprimidos','Cardiovascular','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000096',11500,30),
            ('Metoprolol 50mg','Metoprolol tartrato','Novartis','Caja x 30 comprimidos','Cardiovascular','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000102',6800,25),
            ('Warfarina 5mg','Warfarina sodica','Bristol','Caja x 30 comprimidos','Cardiovascular','MEDICAMENTO','RECETA_RETENIDA','NINGUNA','7801234000119',8400,15),
            ('Metformina 850mg','Metformina HCl','Recalcine','Caja x 30 comprimidos','Diabetes y metabolismo','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000126',3900,40),
            ('Glibenclamida 5mg','Glibenclamida','Saval','Caja x 30 comprimidos','Diabetes y metabolismo','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000133',5100,20),
            ('Alprazolam 0.5mg','Alprazolam','Roche','Caja x 30 comprimidos','Salud mental','MEDICAMENTO','RECETA_RETENIDA','PSICOTROPICO','7801234000140',12800,10),
            ('Clonazepam 0.5mg','Clonazepam','Roche','Caja x 30 comprimidos','Salud mental','MEDICAMENTO','RECETA_RETENIDA','PSICOTROPICO','7801234000157',9600,10),
            ('Sertralina 50mg','Sertralina HCl','Pfizer','Caja x 30 comprimidos','Salud mental','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000164',14200,15),
            ('Morfina 10mg ml','Morfina sulfato','Fresenius','Ampolla 1ml c/5','Salud mental','MEDICAMENTO','RECETA_RETENIDA','ESTUPEFACIENTE','7801234000171',38000,5),
            ('Jeringa 5ml','','Nipro','Bolsa x 10 unidades','Insumos medicos','INSUMO','VENTA_LIBRE','NINGUNA','7801234000188',2800,50),
            ('Gasa esteril 10x10','','Hartmann','Caja x 20 sobres','Insumos medicos','INSUMO','VENTA_LIBRE','NINGUNA','7801234000195',3400,40),
            ('Alcohol 70%','','Pasteur','Frasco 500ml','Insumos medicos','INSUMO','VENTA_LIBRE','NINGUNA','7801234000201',2900,30),
            ('Vitamina C 1000mg','Acido ascorbico','Lab Chile','Caja x 30 comprimidos','Vitaminas y suplementos','MEDICAMENTO','VENTA_LIBRE','NINGUNA','7801234000218',5900,40),
            ('Vitamina D3 2000UI','Colecalciferol','Mintlab','Frasco x 60 capsulas','Vitaminas y suplementos','MEDICAMENTO','VENTA_LIBRE','NINGUNA','7801234000225',8700,30),
            ('Betametasona crema','Betametasona','Schering','Tubo 30g','Dermatologia','MEDICAMENTO','RECETA_SIMPLE','NINGUNA','7801234000232',7200,20),
        ]
        productos={}
        for row in prods_data:
            nombre,principio,lab,pres,cat_key,tipo,nivel,cat_reg,barras,precio,stock_min=row
            p,_=Producto.objects.get_or_create(codigo_barras=barras,defaults=dict(
                nombre=nombre,principio_activo=principio,laboratorio=lab,presentacion=pres,
                categoria=cats[cat_key],tipo=tipo,nivel_control=nivel,categoria_regulatoria=cat_reg,
                precio_venta=precio,stock_minimo=stock_min))
            productos[nombre]=p
        self.stdout.write(f'   {Producto.objects.count()} productos en {Categoria.objects.count()} categorias')
        return cats,productos

    def _crear_convenios(self,categorias):
        self.stdout.write('Creando convenios...')
        convs={}
        for nombre,tipo,desc in [
            ('Isapre Banmedica','ISAPRE',25),('Isapre Cruz Blanca','ISAPRE',20),
            ('Isapre Colmena','ISAPRE',18),('Seguro Complementario Sura','SEGURO_COMPLEMENTARIO',30),
            ('Seguro Complementario Metlife','SEGURO_COMPLEMENTARIO',22),
        ]:
            c,_=Convenio.objects.get_or_create(nombre=nombre,defaults=dict(tipo=tipo,descuento_porcentaje=desc))
            convs[nombre]=c
        for cnombre,catnombre,desc in [
            ('Isapre Banmedica','Cardiovascular',40),('Isapre Banmedica','Diabetes y metabolismo',35),
            ('Isapre Cruz Blanca','Cardiovascular',35),('Seguro Complementario Sura','Salud mental',50),
            ('Seguro Complementario Sura','Vitaminas y suplementos',40),
        ]:
            cat=Categoria.objects.filter(nombre=catnombre).first()
            if cat:
                ConvenioCobertura.objects.get_or_create(convenio=convs[cnombre],categoria=cat,defaults={'descuento_porcentaje':desc})
        self.stdout.write(f'   {Convenio.objects.count()} convenios, {ConvenioCobertura.objects.count()} coberturas')
        return convs

    def _crear_clientes(self,convenios):
        self.stdout.write('Creando clientes...')
        cdata=[
            ('12345678-9','Maria','Gonzalez Soto','+56912345678','mgonzalez@email.cl'),
            ('9876543-2','Juan','Perez Rojas','+56987654321','jperez@email.cl'),
            ('15678901-K','Carmen','Munoz Villanueva','+56911112222','cmunoz@email.cl'),
            ('8901234-5','Pedro','Sanchez Contreras','+56933334444','psanchez@email.cl'),
            ('19234567-8','Ana','Lopez Fuentes','+56955556666','alopez@email.cl'),
            ('11234567-0','Carlos','Ramirez Diaz','+56977778888','cramirez@email.cl'),
            ('16789012-3','Patricia','Torres Medina','+56999990000','ptorres@email.cl'),
            ('7890123-6','Roberto','Herrera Castro','+56911223344','rherrera@email.cl'),
        ]
        clientes=[]
        for rut,nombres,apellidos,tel,email in cdata:
            c,_=Cliente.objects.get_or_create(rut=rut,defaults=dict(nombres=nombres,apellidos=apellidos,telefono=tel,email=email))
            clientes.append(c)
        hoy=date.today(); inicio=hoy-timedelta(days=365)
        for idx,cnombre,num in [
            (0,'Isapre Banmedica','BAN-001234'),(1,'Isapre Cruz Blanca','CB-005678'),
            (2,'Isapre Colmena','COL-003456'),(3,'Seguro Complementario Sura','SUR-007890'),
            (4,'Isapre Banmedica','BAN-002345'),(5,'Isapre Cruz Blanca','CB-006789'),
            (6,'Seguro Complementario Sura','SUR-008901'),
        ]:
            ClienteConvenio.objects.get_or_create(cliente=clientes[idx],convenio=convenios[cnombre],
                defaults=dict(numero_afiliado=num,vigente_desde=inicio))
        self.stdout.write(f'   {Cliente.objects.count()} clientes, {ClienteConvenio.objects.count()} afiliaciones')
        return clientes

    def _crear_inventario(self,admin,productos):
        self.stdout.write('Creando inventario...')
        hoy=date.today()
        prov1, _ = Proveedor.objects.get_or_create(
            nombre='Distribuidora Pharmex Ltda.',
            defaults={'rut': '76.845.120-3', 'giro': 'Distribuidora Farmacéutica e Insumos Médicos', 'contacto_nombre': 'Rodrigo Morales', 'telefono': '+56 2 2456 7890', 'email': 'ventas@pharmex.cl', 'direccion': 'Av. Andrés Bello 2711, Providencia'}
        )
        prov2, _ = Proveedor.objects.get_or_create(
            nombre='Laboratorio Recalcine S.A.',
            defaults={'rut': '91.234.567-8', 'giro': 'Laboratorio Farmacéutico Nacional', 'contacto_nombre': 'María José Soto', 'telefono': '+56 2 2345 6789', 'email': 'pedidos@recalcine.cl', 'direccion': 'Av. Vicuña Mackenna 1020, Ñuñoa'}
        )
        prov3, _ = Proveedor.objects.get_or_create(
            nombre='Roche Chile S.A.',
            defaults={'rut': '80.123.456-7', 'giro': 'Laboratorio Farmacéutico Internacional', 'contacto_nombre': 'Alejandro Valenzuela', 'telefono': '+56 2 2987 6543', 'email': 'suministros@roche.cl', 'direccion': 'Av. Vitacura 5250, Las Condes'}
        )
        prov4, _ = Proveedor.objects.get_or_create(
            nombre='Mintlab S.A. lote antiguo',
            defaults={'rut': '96.543.210-5', 'giro': 'Laboratorio de Medicamentos Genéricos', 'contacto_nombre': 'Camila Henríquez', 'telefono': '+56 2 2876 5432', 'email': 'contacto@mintlab.cl', 'direccion': 'San Ignacio 100, Quilicura'}
        )

        oc1=OrdenCompra.objects.create(proveedor=prov1, numero_factura='FAC-8812', creado_por=admin)
        for nombre,lote_num,dias_vto,qty in [
            ('Paracetamol 500mg','L2025-001',730,200),('Ibuprofeno 400mg','L2025-002',700,150),
            ('Amoxicilina 500mg','L2025-003',500,100),('Azitromicina 500mg','L2025-004',480,60),
            ('Losartan 50mg','L2025-005',800,120),('Metformina 850mg','L2025-006',750,100),
            ('Vitamina C 1000mg','L2025-007',900,150),('Vitamina D3 2000UI','L2025-008',850,100),
            ('Jeringa 5ml','L2025-009',1800,200),('Gasa esteril 10x10','L2025-010',1500,150),
            ('Alcohol 70%','L2025-011',1200,100),
        ]:
            p=productos.get(nombre)
            if p: OrdenCompraDetalle.objects.create(orden=oc1,producto=p,numero_lote=lote_num,fecha_vencimiento=hoy+timedelta(days=dias_vto),cantidad=qty,precio_unitario=int(p.precio_venta*0.6))
        inv_services.recibir_orden_compra(oc1,admin)

        oc2=OrdenCompra.objects.create(proveedor=prov2, numero_factura='FAC-9014', creado_por=admin)
        for nombre,lote_num,dias_vto,qty in [
            ('Ketoprofeno 50mg','L2025-012',540,50),('Diclofenaco 75mg','L2025-013',600,80),
            ('Ciprofloxacino 500mg','L2025-014',520,60),('Atorvastatina 20mg','L2025-015',720,90),
            ('Metoprolol 50mg','L2025-016',680,70),('Warfarina 5mg','L2025-017',760,40),
            ('Glibenclamida 5mg','L2025-018',640,50),('Sertralina 50mg','L2025-019',700,50),
            ('Betametasona crema','L2025-020',580,40),
        ]:
            p=productos.get(nombre)
            if p: OrdenCompraDetalle.objects.create(orden=oc2,producto=p,numero_lote=lote_num,fecha_vencimiento=hoy+timedelta(days=dias_vto),cantidad=qty,precio_unitario=int(p.precio_venta*0.6))
        inv_services.recibir_orden_compra(oc2,admin)

        oc3=OrdenCompra.objects.create(proveedor=prov3, numero_factura='FAC-4421', creado_por=admin)
        for nombre,lote_num,dias_vto,qty in [
            ('Alprazolam 0.5mg','L2025-021',400,30),('Clonazepam 0.5mg','L2025-022',390,30),('Morfina 10mg ml','L2025-023',300,20),
        ]:
            p=productos.get(nombre)
            if p: OrdenCompraDetalle.objects.create(orden=oc3,producto=p,numero_lote=lote_num,fecha_vencimiento=hoy+timedelta(days=dias_vto),cantidad=qty,precio_unitario=int(p.precio_venta*0.5))
        inv_services.recibir_orden_compra(oc3,admin)

        # Lote por vencer (activa alerta)
        p_ibup=productos.get('Ibuprofeno 400mg')
        if p_ibup:
            oc4=OrdenCompra.objects.create(proveedor=prov4, numero_factura='FAC-1102', creado_por=admin)
            OrdenCompraDetalle.objects.create(orden=oc4,producto=p_ibup,numero_lote='L2023-OLD',fecha_vencimiento=hoy+timedelta(days=45),cantidad=20,precio_unitario=1800)
            inv_services.recibir_orden_compra(oc4,admin)

        for nombre,qty in [
            ('Paracetamol 500mg',80),('Ibuprofeno 400mg',50),('Amoxicilina 500mg',40),
            ('Azitromicina 500mg',25),('Losartan 50mg',50),('Metformina 850mg',40),
            ('Vitamina C 1000mg',60),('Vitamina D3 2000UI',40),('Jeringa 5ml',80),
            ('Gasa esteril 10x10',60),('Alcohol 70%',40),('Ketoprofeno 50mg',20),
            ('Diclofenaco 75mg',30),('Ciprofloxacino 500mg',25),('Atorvastatina 20mg',35),
            ('Metoprolol 50mg',30),('Warfarina 5mg',15),('Glibenclamida 5mg',20),
            ('Sertralina 50mg',20),('Betametasona crema',15),('Alprazolam 0.5mg',10),
            ('Clonazepam 0.5mg',10),('Morfina 10mg ml',8),
        ]:
            p=productos.get(nombre)
            if p:
                try: inv_services.traspasar_fefo(p,qty,admin,'Traspaso inicial')
                except: pass
        self.stdout.write(f'   {Lote.objects.count()} lotes, {Stock.objects.count()} registros de stock')

    def _crear_recetas(self,clientes,productos,admin):
        self.stdout.write('Creando recetas...')
        hoy=date.today()
        recetas_data=[
            (0,'5555555-5','Dr. Rodrigo Soto Vega','FISICA','T-20251001',-30,90,[('Losartan 50mg','1 comprimido cada 12 horas',60,30)]),
            (0,'5555555-5','Dr. Rodrigo Soto Vega','FISICA','T-20251002',-15,30,[('Sertralina 50mg','1 comprimido en la manana',30,0)]),
            (1,'6666666-6','Dra. Valentina Mora','FISICA','T-20251003',-10,60,[('Metformina 850mg','1 comprimido con almuerzo',60,0),('Glibenclamida 5mg','1 comprimido antes desayuno',30,0)]),
            (2,'7777777-7','Dr. Francisco Lara','FISICA','R-20251001',-5,30,[('Alprazolam 0.5mg','1 comprimido antes de dormir',30,0)]),
            (3,'5555555-5','Dr. Rodrigo Soto Vega','DIGITAL',None,-3,10,[('Amoxicilina 500mg','1 capsula cada 8 horas',21,0)]),
            (4,'8888888-8','Dra. Carolina Rios','FISICA','T-20251004',-20,60,[('Atorvastatina 20mg','1 comprimido en la noche',30,0),('Losartan 50mg','1 comprimido en la manana',30,0)]),
            (5,'6666666-6','Dra. Valentina Mora','FISICA','R-20251002',-7,30,[('Clonazepam 0.5mg','medio comprimido en la noche',15,0)]),
            (6,'7777777-7','Dr. Francisco Lara','FISICA','T-20251005',-2,15,[('Warfarina 5mg','1 comprimido segun INR',30,0)]),
            (1,'9999999-9','Dr. Pablo Castro','FISICA','R-20251003',-1,30,[('Morfina 10mg ml','1 ampolla segun prescripcion',10,0)]),
        ]
        for cli_idx,med_rut,med_nombre,tipo,folio,offset,vigencia,detalles in recetas_data:
            fe=hoy+timedelta(days=offset); fv=fe+timedelta(days=vigencia)
            try:
                r=Receta.objects.create(cliente=clientes[cli_idx],medico_rut=med_rut,medico_nombre=med_nombre,tipo=tipo,folio=folio,fecha_emision=fe,fecha_vencimiento=fv,creado_por=admin)
                for nombre,posologia,qty_p,qty_d in detalles:
                    p=productos.get(nombre)
                    if p: RecetaDetalle.objects.create(receta=r,producto=p,posologia=posologia,cantidad_prescrita=qty_p,cantidad_dispensada=qty_d)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'   Receta skip: {e}'))
        self.stdout.write(f'   {Receta.objects.count()} recetas, {RecetaDetalle.objects.count()} lineas')

    def _crear_ventas(self,admin,clientes,productos):
        self.stdout.write('Creando ventas...')
        try: caja=ventas_services.abrir_caja(admin,monto_apertura=100000)
        except: caja=Caja.objects.filter(usuario=admin,fecha_cierre__isnull=True).first()
        ventas_ok=0
        # V1 venta libre efectivo
        try:
            v=ventas_services.registrar_venta(caja=caja,vendedor=admin,metodo_pago='EFECTIVO',lineas=[{'producto':productos['Paracetamol 500mg'],'cantidad':2},{'producto':productos['Vitamina C 1000mg'],'cantidad':1},{'producto':productos['Jeringa 5ml'],'cantidad':1}])
            ventas_services.emitir_documento(v,DocumentoTributario.Tipo.BOLETA); ventas_ok+=1
        except Exception as e: self.stdout.write(self.style.WARNING(f'   V1: {e}'))
        # V2 con cliente y convenio debito
        try:
            v=ventas_services.registrar_venta(caja=caja,vendedor=admin,metodo_pago='DEBITO',cliente=clientes[0],lineas=[{'producto':productos['Losartan 50mg'],'cantidad':1},{'producto':productos['Ibuprofeno 400mg'],'cantidad':1}])
            ventas_services.emitir_documento(v,DocumentoTributario.Tipo.BOLETA); ventas_ok+=1
        except Exception as e: self.stdout.write(self.style.WARNING(f'   V2: {e}'))
        # V3 factura transferencia
        try:
            v=ventas_services.registrar_venta(caja=caja,vendedor=admin,metodo_pago='TRANSFERENCIA',cliente=clientes[1],lineas=[{'producto':productos['Metformina 850mg'],'cantidad':2},{'producto':productos['Vitamina D3 2000UI'],'cantidad':1}])
            ventas_services.emitir_documento(v,DocumentoTributario.Tipo.FACTURA); ventas_ok+=1
        except Exception as e: self.stdout.write(self.style.WARNING(f'   V3: {e}'))
        # V4 credito con cliente
        try:
            v=ventas_services.registrar_venta(caja=caja,vendedor=admin,metodo_pago='CREDITO',cliente=clientes[2],lineas=[{'producto':productos['Paracetamol 500mg'],'cantidad':3},{'producto':productos['Gasa esteril 10x10'],'cantidad':2},{'producto':productos['Alcohol 70%'],'cantidad':1}])
            ventas_services.emitir_documento(v,DocumentoTributario.Tipo.BOLETA); ventas_ok+=1
        except Exception as e: self.stdout.write(self.style.WARNING(f'   V4: {e}'))
        # V5 anulada
        try:
            v=ventas_services.registrar_venta(caja=caja,vendedor=admin,metodo_pago='EFECTIVO',lineas=[{'producto':productos['Ibuprofeno 400mg'],'cantidad':1}])
            ventas_services.emitir_documento(v,DocumentoTributario.Tipo.BOLETA)
            ventas_services.anular_venta(v,admin,'Error en transaccion - demo anulacion'); ventas_ok+=1
        except Exception as e: self.stdout.write(self.style.WARNING(f'   V5 anulada: {e}'))
        # V6 con receta
        try:
            rd=RecetaDetalle.objects.filter(receta__cliente=clientes[4],producto=productos['Losartan 50mg'],cantidad_dispensada=0).first()
            if rd:
                v=ventas_services.registrar_venta(caja=caja,vendedor=admin,metodo_pago='DEBITO',cliente=clientes[4],lineas=[{'producto':productos['Losartan 50mg'],'cantidad':1,'receta_detalle':rd}])
                ventas_services.emitir_documento(v,DocumentoTributario.Tipo.BOLETA); ventas_ok+=1
        except Exception as e: self.stdout.write(self.style.WARNING(f'   V6 con receta: {e}'))
        self.stdout.write(f'   {Venta.objects.count()} ventas, {DocumentoTributario.objects.count()} documentos tributarios')
