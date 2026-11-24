"""Tests unitarios para el módulo de inventario.
Cubre: FEFO, traspaso vitrina, ajuste de stock, trazabilidad del ledger
y alertas de stock crítico (RFP-03, RFP-04, RFP-05, RFP-06, RFP-07).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.inventario import services as inv_services
from apps.inventario.models import Lote, MovimientoStock, OrdenCompra, Proveedor, Stock, Ubicacion
from apps.productos.models import Categoria, Producto

Usuario = get_user_model()


def crear_usuario():
    return Usuario.objects.create_user(
        username='tecnico1', password='Test1234!',
        rut='12345678-9', rol='TECNICO_FARMACIA',
    )


def crear_producto(nombre='Paracetamol 500mg', nivel_control='RECETA_SIMPLE'):
    import random
    cat, _ = Categoria.objects.get_or_create(nombre='Analgésicos')
    return Producto.objects.create(
        nombre=nombre, tipo='MEDICAMENTO',
        nivel_control=nivel_control,
        categoria=cat,
        precio_venta=5000,
        codigo_barras=f'780{random.randint(1000000, 9999999)}',
        stock_minimo=10,
    )


def crear_lote(producto, numero='L-001', dias_para_vencer=180, cantidad_bodega=50):
    """Crea un lote con stock en bodega."""
    lote = Lote.objects.create(
        producto=producto,
        numero_lote=numero,
        fecha_vencimiento=date.today() + timedelta(days=dias_para_vencer),
    )
    Stock.objects.create(lote=lote, ubicacion=Ubicacion.BODEGA, cantidad=cantidad_bodega)
    return lote


class TestRecepcionYDisponibilidad(TestCase):
    def test_recibir_orden_pendiente_sin_fecha(self):
        orden = OrdenCompra.objects.create(proveedor=Proveedor.objects.create(nombre='Proveedor'))
        producto = crear_producto()
        linea = orden.detalles.create(producto=producto, cantidad=2, precio_unitario=100)
        usuario = crear_usuario()
        with self.assertRaisesMessage(ValueError, 'Ingresa el vencimiento'):
            inv_services.recibir_orden_compra(orden, usuario)
        self.assertFalse(Stock.objects.exists())
        fecha = timezone.localdate() + timedelta(days=20)
        inv_services.recibir_orden_compra(orden, usuario, {f'vencimiento_{linea.pk}': fecha.isoformat()})
        self.assertEqual(Lote.objects.get().fecha_vencimiento, fecha)
        self.assertEqual(Stock.objects.get().cantidad, 2)

    def test_chat_consulta_stock_vigente_por_ubicacion(self):
        from apps.panel.views import consultar_disponibilidad
        producto = crear_producto()
        vigente = crear_lote(producto, cantidad_bodega=12)
        crear_lote(producto, numero='CAD', dias_para_vencer=-2, cantidad_bodega=50)
        Stock.objects.create(lote=vigente, ubicacion=Ubicacion.VITRINA, cantidad=3)
        respuesta = consultar_disponibilidad('¿Hay paracetamol?')
        self.assertIn('3 en vitrina, 12 en bodega', respuesta)
        self.assertEqual(respuesta, consultar_disponibilidad(producto.codigo_barras))


class TestTraspasoBodegaVitrina(TestCase):
    """Verifica que el traspaso mueva stock entre ubicaciones y registre
    el movimiento en el ledger (trazabilidad RFP-04)."""

    def setUp(self):
        self.usuario = crear_usuario()
        self.producto = crear_producto()
        self.lote = crear_lote(self.producto, cantidad_bodega=50)

    def test_traspaso_decrementa_bodega(self):
        inv_services.traspasar_stock(self.lote, 20, self.usuario)
        stock_bodega = Stock.objects.get(lote=self.lote, ubicacion=Ubicacion.BODEGA)
        self.assertEqual(stock_bodega.cantidad, 30)

    def test_venta_excluye_lote_vencido_con_stock_en_vitrina(self):
        vencido = crear_lote(self.producto, numero='VENCIDO', dias_para_vencer=-1)
        Stock.objects.create(lote=vencido, ubicacion=Ubicacion.VITRINA, cantidad=20)
        self.assertRaises(ValueError, inv_services.descontar_venta_fefo,
                          self.producto, 1, self.usuario)

    def test_traspaso_incrementa_vitrina(self):
        inv_services.traspasar_stock(self.lote, 20, self.usuario)
        stock_vitrina = Stock.objects.get(lote=self.lote, ubicacion=Ubicacion.VITRINA)
        self.assertEqual(stock_vitrina.cantidad, 20)

    def test_traspaso_registra_movimiento(self):
        inv_services.traspasar_stock(self.lote, 15, self.usuario)
        movs = MovimientoStock.objects.filter(lote=self.lote, tipo=MovimientoStock.Tipo.TRASPASO)
        self.assertEqual(movs.count(), 1)

    def test_traspaso_sin_stock_suficiente_lanza_error(self):
        with self.assertRaises(ValueError):
            inv_services.traspasar_stock(self.lote, 200, self.usuario)

    def test_traspaso_cantidad_cero_lanza_error(self):
        with self.assertRaises(ValueError):
            inv_services.traspasar_stock(self.lote, 0, self.usuario)


class TestAjusteStock(TestCase):
    """Verifica el ajuste de stock (corrección manual), con registro en ledger
    (RFP-04, trazabilidad RFP-11)."""

    def setUp(self):
        self.usuario = crear_usuario()
        self.producto = crear_producto('Ibuprofeno 400mg')
        self.lote = crear_lote(self.producto, cantidad_bodega=30)
        Stock.objects.create(lote=self.lote, ubicacion=Ubicacion.VITRINA, cantidad=10)

    def test_ajuste_positivo_incrementa_stock(self):
        inv_services.registrar_ajuste(self.lote, Ubicacion.VITRINA, 5, self.usuario, 'Ajuste positivo')
        stock = Stock.objects.get(lote=self.lote, ubicacion=Ubicacion.VITRINA)
        self.assertEqual(stock.cantidad, 15)

    def test_ajuste_negativo_decrementa_stock(self):
        inv_services.registrar_ajuste(self.lote, Ubicacion.VITRINA, -3, self.usuario, 'Merma')
        stock = Stock.objects.get(lote=self.lote, ubicacion=Ubicacion.VITRINA)
        self.assertEqual(stock.cantidad, 7)

    def test_ajuste_deja_negativo_lanza_error(self):
        with self.assertRaises(ValueError):
            inv_services.registrar_ajuste(self.lote, Ubicacion.VITRINA, -100, self.usuario, 'Error')

    def test_ajuste_registra_movimiento(self):
        inv_services.registrar_ajuste(self.lote, Ubicacion.VITRINA, 2, self.usuario, 'Inventario físico')
        movs = MovimientoStock.objects.filter(lote=self.lote, tipo=MovimientoStock.Tipo.AJUSTE_POSITIVO)
        self.assertGreaterEqual(movs.count(), 1)


class TestFEFO(TestCase):
    """Verifica que la venta descuenta stock priorizando el lote con fecha
    de vencimiento más próxima (FEFO — RFP-05)."""

    def setUp(self):
        self.usuario = crear_usuario()
        self.producto = crear_producto('Amoxicilina 500mg')

        # Lote A: vence en 30 días (debe salir primero)
        self.lote_proximo = Lote.objects.create(
            producto=self.producto,
            numero_lote='FEFO-A',
            fecha_vencimiento=date.today() + timedelta(days=30),
        )
        Stock.objects.create(lote=self.lote_proximo, ubicacion=Ubicacion.VITRINA, cantidad=5)

        # Lote B: vence en 180 días (debe salir segundo)
        self.lote_lejano = Lote.objects.create(
            producto=self.producto,
            numero_lote='FEFO-B',
            fecha_vencimiento=date.today() + timedelta(days=180),
        )
        Stock.objects.create(lote=self.lote_lejano, ubicacion=Ubicacion.VITRINA, cantidad=20)

    def test_fefo_prioriza_vencimiento_proximo(self):
        """Al descontar 5 unidades, deben salir todas del lote próximo a vencer."""
        consumo = inv_services.descontar_venta_fefo(self.producto, 5, self.usuario, 'Test FEFO')
        lotes_consumidos = [lote for lote, _ in consumo]
        self.assertIn(self.lote_proximo, lotes_consumidos)
        # El lote lejano no debería tocarse para 5 unidades
        self.assertNotIn(self.lote_lejano, lotes_consumidos)

    def test_fefo_consume_ambos_lotes_si_necesario(self):
        """Al pedir 8 unidades, se agotan 5 del lote próximo y 3 del lejano."""
        consumo = inv_services.descontar_venta_fefo(self.producto, 8, self.usuario, 'Test FEFO multi')
        lotes_consumidos = {lote for lote, _ in consumo}
        self.assertIn(self.lote_proximo, lotes_consumidos)
        self.assertIn(self.lote_lejano, lotes_consumidos)

    def test_fefo_sin_stock_suficiente_lanza_error(self):
        with self.assertRaises(ValueError):
            inv_services.descontar_venta_fefo(self.producto, 1000, self.usuario, 'Test exceso')


class TestLoteVencimiento(TestCase):
    """Tests para propiedades del modelo Lote relacionadas con vencimiento."""

    def setUp(self):
        self.producto = crear_producto()

    def test_dias_para_vencer_correcto(self):
        lote = Lote(
            producto=self.producto,
            numero_lote='V-001',
            fecha_vencimiento=date.today() + timedelta(days=45),
        )
        self.assertEqual(lote.dias_para_vencer, 45)

    def test_esta_por_vencer_con_90_dias(self):
        lote = Lote(
            producto=self.producto,
            numero_lote='V-002',
            fecha_vencimiento=date.today() + timedelta(days=60),
        )
        self.assertTrue(lote.esta_por_vencer(90))
        self.assertFalse(lote.esta_por_vencer(30))
