"""Tests unitarios para el módulo de recetas.
Cubre: Vigencia de recetas (RFP-09), validaciones de prescripción,
saldo de recetas para tratamientos crónicos y control de dispensación
con trazabilidad de retiro (paciente o tercero).
"""
from datetime import date, timedelta
import random

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.productos.models import Categoria, Producto
from apps.recetas import services as recetas_services
from apps.recetas.models import DispensacionReceta, Receta, RecetaDetalle

Usuario = get_user_model()


def crear_usuario():
    return Usuario.objects.create_user(
        username=f'quimico_{random.randint(100, 999)}',
        password='TestPassword123!',
        rut=f'{random.randint(10000000, 25000000)}-{random.randint(0, 9)}',
        rol='FARMACEUTICO',
    )


def crear_cliente():
    return Cliente.objects.create(
        rut=f'{random.randint(10000000, 25000000)}-{random.randint(0, 9)}',
        nombres='María',
        apellidos='González',
        telefono='+56998765432',
        email='maria.gonzalez@example.com',
    )


def crear_producto(nombre='Losartán 50mg', nivel_control='RECETA_SIMPLE'):
    cat, _ = Categoria.objects.get_or_create(nombre='Cardiovasculares')
    return Producto.objects.create(
        nombre=nombre,
        tipo='MEDICAMENTO',
        nivel_control=nivel_control,
        categoria=cat,
        precio_venta=4500,
        codigo_barras=f'780{random.randint(1000000, 9999999)}',
        stock_minimo=10,
    )


class TestRecetaVigencia(TestCase):
    """Pruebas de vigencia y fechas de emisión/vencimiento (RFP-09)."""

    def setUp(self):
        self.usuario = crear_usuario()
        self.cliente = crear_cliente()

    def test_receta_vigente(self):
        receta = Receta.objects.create(
            cliente=self.cliente,
            medico_rut='12345678-5',
            medico_nombre='Dra. Marcela Rojas',
            tipo=Receta.Tipo.FISICA,
            fecha_emision=date.today() - timedelta(days=5),
            fecha_vencimiento=date.today() + timedelta(days=25),
            creado_por=self.usuario,
        )
        self.assertTrue(receta.esta_vigente)

    def test_receta_vencida_no_esta_vigente(self):
        receta = Receta.objects.create(
            cliente=self.cliente,
            medico_rut='12345678-5',
            medico_nombre='Dra. Marcela Rojas',
            tipo=Receta.Tipo.FISICA,
            fecha_emision=date.today() - timedelta(days=60),
            fecha_vencimiento=date.today() - timedelta(days=1),
            creado_por=self.usuario,
        )
        self.assertFalse(receta.esta_vigente)

    def test_fecha_vencimiento_anterior_a_emision_invalida(self):
        receta = Receta(
            cliente=self.cliente,
            medico_rut='12345678-5',
            medico_nombre='Dra. Marcela Rojas',
            tipo=Receta.Tipo.DIGITAL,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today() - timedelta(days=5),
            creado_por=self.usuario,
        )
        with self.assertRaises(ValidationError):
            receta.clean()


class TestRecetaDetalle(TestCase):
    """Pruebas para líneas de receta y cálculo de saldos."""

    def setUp(self):
        self.usuario = crear_usuario()
        self.cliente = crear_cliente()
        self.receta = Receta.objects.create(
            cliente=self.cliente,
            medico_rut='12345678-5',
            medico_nombre='Dra. Marcela Rojas',
            tipo=Receta.Tipo.FISICA,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today() + timedelta(days=30),
            creado_por=self.usuario,
        )

    def test_producto_venta_libre_no_permite_receta(self):
        cat_libre, _ = Categoria.objects.get_or_create(nombre='Varios')
        prod_libre = Producto.objects.create(
            nombre='Vitamina C 1g',
            tipo='MEDICAMENTO',
            nivel_control='VENTA_LIBRE',
            categoria=cat_libre,
            precio_venta=2000,
            codigo_barras=f'780{random.randint(1000000, 9999999)}',
        )
        detalle = RecetaDetalle(
            receta=self.receta,
            producto=prod_libre,
            cantidad_prescrita=3,
        )
        with self.assertRaises(ValidationError):
            detalle.clean()

    def test_saldo_inicial_y_con_saldo(self):
        producto = crear_producto('Enalapril 10mg')
        detalle = RecetaDetalle.objects.create(
            receta=self.receta,
            producto=producto,
            cantidad_prescrita=60,
            cantidad_dispensada=0,
        )
        self.assertEqual(detalle.saldo, 60)
        self.assertTrue(detalle.con_saldo)


class TestDispensacionReceta(TestCase):
    """Pruebas del servicio de dispensación y trazabilidad de retiro."""

    def setUp(self):
        self.usuario = crear_usuario()
        self.cliente = crear_cliente()
        self.producto = crear_producto('Metformina 850mg')
        self.receta = Receta.objects.create(
            cliente=self.cliente,
            medico_rut='12345678-5',
            medico_nombre='Dr. Pablo Neruda',
            tipo=Receta.Tipo.FISICA,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today() + timedelta(days=90),
            creado_por=self.usuario,
        )
        self.detalle = RecetaDetalle.objects.create(
            receta=self.receta,
            producto=self.producto,
            cantidad_prescrita=90,
            cantidad_dispensada=0,
        )

    def test_dispensacion_parcial_actualiza_saldo(self):
        disp = recetas_services.dispensar(
            self.detalle, cantidad=30, usuario=self.usuario, observacion='Primera entrega mensual',
        )
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.cantidad_dispensada, 30)
        self.assertEqual(self.detalle.saldo, 60)
        self.assertEqual(disp.cantidad, 30)

    def test_dispensacion_excede_saldo_lanza_error(self):
        with self.assertRaises(ValueError):
            recetas_services.dispensar(self.detalle, cantidad=100, usuario=self.usuario)

    def test_dos_entregas_validan_el_saldo_actual(self):
        segunda_linea = RecetaDetalle.objects.get(pk=self.detalle.pk)
        recetas_services.dispensar(self.detalle, cantidad=60, usuario=self.usuario)
        with self.assertRaisesMessage(ValueError, 'Saldo insuficiente'):
            recetas_services.dispensar(segunda_linea, cantidad=40, usuario=self.usuario)
        segunda_linea.refresh_from_db()
        self.assertEqual(segunda_linea.saldo, 30)

    def test_dispensacion_receta_vencida_lanza_error(self):
        self.receta.fecha_vencimiento = date.today() - timedelta(days=1)
        self.receta.save()
        with self.assertRaises(ValueError):
            recetas_services.dispensar(self.detalle, cantidad=10, usuario=self.usuario)

    def test_dispensacion_retirada_por_tercero(self):
        tercero = {
            'nombre': 'Carlos González',
            'rut': '18765432-1',
            'relacion': 'Hijo',
        }
        disp = recetas_services.dispensar(
            self.detalle, cantidad=30, usuario=self.usuario, observacion='Retiro familiar', retirado_por=tercero,
        )
        self.assertEqual(disp.retirado_por_nombre, 'Carlos González')
        self.assertEqual(disp.retirado_por_relacion, 'Hijo')
