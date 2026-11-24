"""Tests unitarios para el módulo de ventas.
Cubre: Apertura/cierre y cuadratura de caja (RFP-06),
registro de venta con descuento FEFO de vitrina,
validación y descuento de receta médica (RFP-09),
acumulación de puntos de fidelización,
anulación y reintegro de stock, y reglas de documentos tributarios (RFP-07).
"""
from datetime import date, timedelta
import random

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.inventario.models import Lote, Stock, Ubicacion
from apps.productos.models import Categoria, Producto
from apps.recetas.models import Receta, RecetaDetalle
from apps.ventas import services as ventas_services
from apps.ventas.forms import FinalizarVentaForm
from apps.ventas.models import Caja, DocumentoTributario, Venta

Usuario = get_user_model()


def crear_usuario(username='cajero1'):
    return Usuario.objects.create_user(
        username=username,
        password='TestPassword123!',
        rut=f'{random.randint(10000000, 25000000)}-{random.randint(0, 9)}',
        rol='CAJERO',
    )


def crear_cliente(rut='11111111-1'):
    return Cliente.objects.create(
        rut=rut,
        nombres='Juan',
        apellidos='Pérez',
        telefono='+56912345678',
        email='juan.perez@example.com',
    )


def crear_producto(nombre='Paracetamol 500mg', nivel_control='VENTA_LIBRE', precio=3000):
    cat, _ = Categoria.objects.get_or_create(nombre='Analgésicos')
    return Producto.objects.create(
        nombre=nombre,
        tipo='MEDICAMENTO',
        nivel_control=nivel_control,
        categoria=cat,
        precio_venta=precio,
        codigo_barras=f'780{random.randint(1000000, 9999999)}',
        stock_minimo=10,
    )


def crear_lote_con_stock_vitrina(producto, cantidad=50, dias_vencimiento=120):
    lote = Lote.objects.create(
        producto=producto,
        numero_lote=f'L-{random.randint(100, 999)}',
        fecha_vencimiento=date.today() + timedelta(days=dias_vencimiento),
    )
    Stock.objects.create(lote=lote, ubicacion=Ubicacion.VITRINA, cantidad=cantidad)
    return lote


class TestCaja(TestCase):
    """Pruebas de apertura, flujo y cierre de caja con cuadratura."""

    def setUp(self):
        self.cajero = crear_usuario('cajero_caja')

    def test_abrir_caja_exitoso(self):
        caja = ventas_services.abrir_caja(self.cajero, monto_apertura=50000)
        self.assertTrue(caja.esta_abierta)
        self.assertEqual(caja.monto_apertura, 50000)

    def test_abrir_caja_duplicada_lanza_error(self):
        ventas_services.abrir_caja(self.cajero, monto_apertura=50000)
        with self.assertRaises(ValueError):
            ventas_services.abrir_caja(self.cajero, monto_apertura=20000)

    def test_cerrar_caja_calcula_diferencia(self):
        caja = ventas_services.abrir_caja(self.cajero, monto_apertura=50000)
        # Sin ventas, el sistema espera 50000
        ventas_services.cerrar_caja(caja, monto_declarado=48000, usuario=self.cajero)
        caja.refresh_from_db()
        self.assertFalse(caja.esta_abierta)
        self.assertEqual(caja.monto_cierre_sistema, 50000)
        self.assertEqual(caja.monto_cierre_declarado, 48000)
        self.assertEqual(caja.diferencia, -2000)  # descuadre negativo de $2.000


class TestVenta(TestCase):
    """Pruebas para el registro de ventas, reglas de control y anulación."""

    def setUp(self):
        self.cajero = crear_usuario('cajero_ventas')
        self.caja = ventas_services.abrir_caja(self.cajero, monto_apertura=100000)
        self.cliente = crear_cliente('22222222-2')
        self.producto_libre = crear_producto('Ibuprofeno 400mg', nivel_control='VENTA_LIBRE', precio=4000)
        self.lote_libre = crear_lote_con_stock_vitrina(self.producto_libre, cantidad=20)

    def test_venta_venta_libre_descuenta_stock_vitrina(self):
        lineas = [{'producto': self.producto_libre, 'cantidad': 3}]
        venta = ventas_services.registrar_venta(
            caja=self.caja,
            vendedor=self.cajero,
            metodo_pago=Venta.MetodoPago.EFECTIVO,
            lineas=lineas,
            cliente=self.cliente,
        )
        self.assertEqual(venta.detalles.count(), 1)
        stock_vitrina = Stock.objects.get(lote=self.lote_libre, ubicacion=Ubicacion.VITRINA)
        self.assertEqual(stock_vitrina.cantidad, 17)

    def test_venta_requiere_receta_falla_sin_receta(self):
        producto_controlado = crear_producto('Clonazepam 2mg', nivel_control='RECETA_RETENIDA')
        crear_lote_con_stock_vitrina(producto_controlado, cantidad=10)
        lineas = [{'producto': producto_controlado, 'cantidad': 1}]

        with self.assertRaises(ValueError):
            ventas_services.registrar_venta(
                caja=self.caja,
                vendedor=self.cajero,
                metodo_pago=Venta.MetodoPago.EFECTIVO,
                lineas=lineas,
            )

    def test_venta_con_receta_descuenta_saldo(self):
        producto_receta = crear_producto('Amoxicilina 500mg', nivel_control='RECETA_SIMPLE', precio=6000)
        crear_lote_con_stock_vitrina(producto_receta, cantidad=20)

        receta = Receta.objects.create(
            cliente=self.cliente,
            medico_rut='9999999-9',
            medico_nombre='Dr. Soto',
            tipo=Receta.Tipo.DIGITAL,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today() + timedelta(days=30),
            creado_por=self.cajero,
        )
        receta_detalle = RecetaDetalle.objects.create(
            receta=receta,
            producto=producto_receta,
            posologia='1 cada 8 hrs',
            cantidad_prescrita=10,
        )

        lineas = [{'producto': producto_receta, 'cantidad': 4, 'receta_detalle': receta_detalle}]
        venta = ventas_services.registrar_venta(
            caja=self.caja,
            vendedor=self.cajero,
            metodo_pago=Venta.MetodoPago.DEBITO,
            lineas=lineas,
            cliente=self.cliente,
        )

        receta_detalle.refresh_from_db()
        self.assertEqual(receta_detalle.cantidad_dispensada, 4)
        self.assertEqual(receta_detalle.saldo, 6)
        self.assertEqual(receta_detalle.dispensaciones.count(), 1)

    def test_venta_acumula_puntos_de_fidelizacion(self):
        # 2 unidades a $4.000 = $8.000 -> 80 puntos (1 por cada $100)
        lineas = [{'producto': self.producto_libre, 'cantidad': 2}]
        ventas_services.registrar_venta(
            caja=self.caja,
            vendedor=self.cajero,
            metodo_pago=Venta.MetodoPago.EFECTIVO,
            lineas=lineas,
            cliente=self.cliente,
        )
        self.assertEqual(self.cliente.saldo_puntos, 80)

    def test_anulacion_con_dos_solicitudes_restituye_una_vez(self):
        venta = ventas_services.registrar_venta(self.caja, self.cajero, Venta.MetodoPago.EFECTIVO,
                                                [{'producto': self.producto_libre, 'cantidad': 2}], self.cliente)
        segunda = Venta.objects.get(pk=venta.pk)
        ventas_services.anular_venta(venta, self.cajero, 'Devolución')
        with self.assertRaisesMessage(ValueError, 'ya está anulada'):
            ventas_services.anular_venta(segunda, self.cajero, 'Reintento')
        self.assertEqual(self.cliente.saldo_puntos, 0)
        self.assertEqual(self.cliente.puntos_fidelizacion.count(), 2)
        self.assertEqual(self.lote_libre.stock_total, 20)

    def test_cliente_obligatorio_solo_para_factura(self):
        datos = {'metodo_pago': Venta.MetodoPago.EFECTIVO}
        self.assertTrue(FinalizarVentaForm(datos).is_valid())
        self.assertIn('cliente', FinalizarVentaForm({**datos, 'emitir_factura': True}).errors)
        self.assertTrue(FinalizarVentaForm({**datos, 'emitir_factura': True, 'cliente': self.cliente.pk}).is_valid())

    def test_anular_venta_reintegra_stock(self):
        lineas = [{'producto': self.producto_libre, 'cantidad': 5}]
        venta = ventas_services.registrar_venta(
            caja=self.caja,
            vendedor=self.cajero,
            metodo_pago=Venta.MetodoPago.EFECTIVO,
            lineas=lineas,
        )
        # Stock vitrina bajó a 15
        stock_post_venta = Stock.objects.get(lote=self.lote_libre, ubicacion=Ubicacion.VITRINA)
        self.assertEqual(stock_post_venta.cantidad, 15)

        # Anulación
        ventas_services.anular_venta(venta, usuario=self.cajero, motivo='Cliente desistió de la compra')
        venta.refresh_from_db()
        self.assertEqual(venta.estado, Venta.Estado.ANULADA)

        # Stock vitrina se restituyó a 20
        stock_post_anulacion = Stock.objects.get(lote=self.lote_libre, ubicacion=Ubicacion.VITRINA)
        self.assertEqual(stock_post_anulacion.cantidad, 20)

    def test_anular_venta_ya_anulada_lanza_error(self):
        lineas = [{'producto': self.producto_libre, 'cantidad': 1}]
        venta = ventas_services.registrar_venta(
            caja=self.caja,
            vendedor=self.cajero,
            metodo_pago=Venta.MetodoPago.EFECTIVO,
            lineas=lineas,
        )
        ventas_services.anular_venta(venta, usuario=self.cajero, motivo='Primera anulación')
        with self.assertRaises(ValueError):
            ventas_services.anular_venta(venta, usuario=self.cajero, motivo='Segunda anulación')


class TestDocumentoTributario(TestCase):
    """Validaciones de boletas y facturas simuladas."""

    def setUp(self):
        self.cajero = crear_usuario('cajero_doc')
        self.caja = ventas_services.abrir_caja(self.cajero, monto_apertura=50000)
        self.producto = crear_producto('Aspirina 100mg', precio=2000)
        crear_lote_con_stock_vitrina(self.producto, cantidad=10)

    def test_factura_sin_cliente_lanza_error_validacion(self):
        lineas = [{'producto': self.producto, 'cantidad': 1}]
        # Venta anónima (sin cliente)
        venta = ventas_services.registrar_venta(
            caja=self.caja,
            vendedor=self.cajero,
            metodo_pago=Venta.MetodoPago.EFECTIVO,
            lineas=lineas,
            cliente=None,
        )
        doc = DocumentoTributario(
            venta=venta,
            tipo=DocumentoTributario.Tipo.FACTURA,
            folio=1001,
        )
        with self.assertRaises(ValidationError):
            doc.clean()

    def test_boleta_creacion_exitosa(self):
        lineas = [{'producto': self.producto, 'cantidad': 1}]
        venta = ventas_services.registrar_venta(
            caja=self.caja,
            vendedor=self.cajero,
            metodo_pago=Venta.MetodoPago.EFECTIVO,
            lineas=lineas,
        )
        doc = DocumentoTributario.objects.create(
            venta=venta,
            tipo=DocumentoTributario.Tipo.BOLETA,
            folio=2001,
        )
        self.assertEqual(doc.tipo, DocumentoTributario.Tipo.BOLETA)
        self.assertEqual(doc.folio, 2001)


class TestActualizarCantidadView(TestCase):
    """Pruebas para incrementar/decrementar cantidad en el carrito con y sin AJAX."""

    def setUp(self):
        self.cajero = crear_usuario('cajero_carrito')
        self.producto = crear_producto('Paracetamol 500mg', precio=3000)
        crear_lote_con_stock_vitrina(self.producto, cantidad=5)
        self.client.force_login(self.cajero)

    def test_incrementar_cantidad_ajax(self):
        # Preparar carrito en sesión
        session = self.client.session
        session['carrito_venta'] = [{'producto_id': self.producto.pk, 'cantidad': 1, 'receta_detalle_id': None}]
        session.save()

        # Enviar petición AJAX para incrementar
        response = self.client.post(
            f'/ventas/pos/cantidad/0/',
            {'accion': 'incrementar'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['cantidad'], 2)
        self.assertEqual(data['subtotal'], '$6000')
        self.assertFalse(data['deshabilitar_menos'])

    def test_incrementar_superando_stock_retorna_error_400(self):
        session = self.client.session
        session['carrito_venta'] = [{'producto_id': self.producto.pk, 'cantidad': 5, 'receta_detalle_id': None}]
        session.save()

        response = self.client.post(
            f'/ventas/pos/cantidad/0/',
            {'accion': 'incrementar'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('Stock insuficiente', data['error'])

