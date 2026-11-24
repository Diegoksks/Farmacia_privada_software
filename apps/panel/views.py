from datetime import timedelta
import re

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from apps.inventario.models import Lote, Ubicacion
from apps.productos.models import Producto
from apps.recetas.models import RecetaDetalle
from apps.usuarios.models import Usuario
from apps.ventas.models import Caja, Venta, VentaDetalle

DIAS_ALERTA_VENCIMIENTO = 90


def _modulos_visibles(usuario):
    """Tarjetas del panel filtradas por los permisos reales del usuario, de
    modo que cada rol vea solo lo que efectivamente puede hacer. Las acciones
    apuntan a las vistas propias cuando existen, y al admin para el resto."""
    catalogo = [
        {
            'nombre': 'Punto de venta',
            'icono': 'bi-cash-coin',
            'descripcion': 'Registrar ventas, emitir boletas y controlar la caja diaria.',
            'permiso': 'ventas.add_venta',
            'acciones': [
                {'label': 'Vender', 'url': reverse('ventas:punto_venta'), 'primaria': True},
                {'label': 'Abrir caja', 'url': reverse('ventas:abrir_caja')},
                {'label': 'Cerrar caja', 'url': reverse('ventas:cerrar_caja')},
            ],
        },
        {
            'nombre': 'Historial de ventas',
            'icono': 'bi-receipt',
            'descripcion': 'Consultar ventas realizadas, documentos emitidos y cierres de caja.',
            'permiso': 'ventas.view_venta',
            'acciones': [
                {'label': 'Ventas', 'url': reverse('ventas:venta_lista'), 'primaria': True},
                {'label': 'Cajas', 'url': reverse('ventas:caja_lista'), 'permiso': 'ventas.view_caja'},
                {'label': 'Documentos', 'url': reverse('ventas:documento_lista')},
            ],
        },
        {
            'nombre': 'Movimientos de inventario',
            'icono': 'bi-arrow-left-right',
            'descripcion': 'Reponer vitrina desde bodega con criterio FEFO y corregir stock por mermas.',
            'permiso': 'inventario.add_movimientostock',
            'acciones': [
                {'label': 'Traspaso a vitrina', 'url': reverse('inventario:traspaso'), 'primaria': True},
                {'label': 'Ajuste de stock', 'url': reverse('inventario:ajuste')},
            ],
        },
        {
            'nombre': 'Inventario y lotes',
            'icono': 'bi-boxes',
            'descripcion': 'Stock por bodega y vitrina, lotes con fecha de vencimiento y trazabilidad.',
            'permiso': 'inventario.view_lote',
            'acciones': [
                {'label': 'Lotes y Stock', 'url': reverse('inventario:lote_lista'), 'primaria': True},
                {
                    'label': 'Movimientos', 'url': reverse('inventario:movimiento_lista'),
                    'permiso': 'inventario.view_movimientostock',
                },
            ],
        },
        {
            'nombre': 'Órdenes de compra',
            'icono': 'bi-truck',
            'descripcion': 'Comprar a proveedores y recibir mercadería, que ingresa a bodega por lote.',
            'permiso': 'inventario.view_ordencompra',
            'acciones': [
                {'label': 'Ver órdenes', 'url': reverse('inventario:orden_lista'), 'primaria': True},
                {
                    'label': 'Nueva orden', 'url': reverse('inventario:orden_crear'),
                    'permiso': 'inventario.add_ordencompra',
                },
            ],
        },
        {
            'nombre': 'Inteligencia de Inventario',
            'icono': 'bi-robot',
            'descripcion': 'Predicción de demanda y cálculo de días de stock restante mediante Machine Learning.',
            'permiso': 'inventario.view_movimientostock',
            'acciones': [
                {'label': 'Ver proyecciones', 'url': reverse('inventario:proyeccion_demanda'), 'primaria': True},
            ],
        },
        {
            'nombre': 'Catálogo de productos',
            'icono': 'bi-capsule',
            'descripcion': 'Medicamentos e insumos, con su nivel de control y categoría regulatoria.',
            'permiso': 'productos.view_producto',
            'acciones': [
                {'label': 'Productos', 'url': reverse('productos:lista'), 'primaria': True},
                {'label': 'Categorías', 'url': reverse('productos:categoria_lista')},
                {'label': 'Nuevo producto', 'url': reverse('productos:crear'), 'permiso': 'productos.add_producto'},
            ],
        },
        {
            'nombre': 'Recetas',
            'icono': 'bi-file-medical',
            'descripcion': 'Registrar y validar recetas, controlar vigencia y saldo por tratamiento.',
            'permiso': 'recetas.view_receta',
            'acciones': [
                {'label': 'Ver recetas', 'url': reverse('recetas:lista'), 'primaria': True},
                {'label': 'Nueva receta', 'url': reverse('recetas:crear'), 'permiso': 'recetas.add_receta'},
                {
                    'label': 'Dispensaciones', 'url': reverse('recetas:dispensacion_lista'),
                    'permiso': 'recetas.view_dispensacionreceta',
                },
            ],
        },
        {
            'nombre': 'Medicamentos controlados',
            'icono': 'bi-shield-lock',
            'descripcion': 'Libro digital de control de estupefacientes y psicotrópicos (reglamento ISP).',
            'permiso': 'recetas.view_librocontrol',
            'acciones': [
                {'label': 'Libro de control', 'url': reverse('recetas:libro_control'), 'primaria': True},
            ],
        },
        {
            'nombre': 'Clientes',
            'icono': 'bi-people',
            'descripcion': 'Datos de clientes y pacientes identificados por RUT.',
            'permiso': 'clientes.view_cliente',
            'acciones': [
                {'label': 'Clientes', 'url': reverse('clientes:lista'), 'primaria': True},
                {'label': 'Nuevo cliente', 'url': reverse('clientes:crear'), 'permiso': 'clientes.add_cliente'},
            ],
        },
        {
            'nombre': 'Convenios',
            'icono': 'bi-hospital',
            'descripcion': 'Isapres y seguros complementarios, con descuentos por categoría y afiliaciones.',
            'permiso': 'convenios.view_convenio',
            'acciones': [
                {'label': 'Ver convenios', 'url': reverse('convenios:lista'), 'primaria': True},
                {'label': 'Nuevo convenio', 'url': reverse('convenios:crear'), 'permiso': 'convenios.add_convenio'},
                {
                    'label': 'Afiliaciones', 'url': reverse('convenios:afiliaciones_lista'),
                    'permiso': 'convenios.view_clienteconvenio',
                },
            ],
        },
        {
            'nombre': 'Reportes e indicadores',
            'icono': 'bi-graph-up',
            'descripcion': 'Dashboard comercial y reportes exportables en PDF y Excel.',
            'rol': Usuario.Rol.ADMINISTRADOR,
            'acciones': [
                {'label': 'Dashboard', 'url': reverse('reportes:dashboard'), 'primaria': True},
                {'label': 'Reporte de ventas', 'url': reverse('reportes:reporte_ventas')},
                {'label': 'Reporte de inventario', 'url': reverse('reportes:reporte_inventario')},
            ],
        },
        {
            'nombre': 'Usuarios y roles',
            'icono': 'bi-person-gear',
            'descripcion': 'Crear, modificar y desactivar usuarios; revisar permisos por rol.',
            'permiso': 'usuarios.view_usuario',
            'acciones': [
                {'label': 'Usuarios', 'url': reverse('usuarios:lista'), 'primaria': True},
                {
                    'label': 'Nuevo usuario', 'url': reverse('usuarios:crear'),
                    'permiso': 'usuarios.add_usuario',
                },
                {'label': 'Roles y permisos', 'url': reverse('usuarios:grupo_lista'), 'permiso': 'auth.view_group'},
            ],
        },
    ]

    visibles = []
    for modulo in catalogo:
        if modulo.get('rol') and usuario.rol != modulo['rol']:
            continue
        if modulo.get('permiso') and not usuario.has_perm(modulo['permiso']):
            continue
        acciones = [
            accion for accion in modulo['acciones']
            if not accion.get('permiso') or usuario.has_perm(accion['permiso'])
        ]
        if acciones:
            visibles.append({**modulo, 'acciones': acciones})
    return visibles


def _indicadores(usuario):
    """Cifras rápidas acotadas a lo que el usuario puede ver: montos solo para
    el Administrador, alertas operativas para quienes manejan inventario."""
    indicadores = []
    hoy = timezone.localdate()

    if usuario.has_perm('ventas.add_venta'):
        caja = Caja.objects.filter(usuario=usuario, fecha_cierre__isnull=True).first()
        indicadores.append({
            'etiqueta': 'Mi caja',
            'valor': 'Abierta' if caja else 'Cerrada',
            'detalle': f'Apertura ${caja.monto_apertura}' if caja else 'Debes abrir caja para vender',
            'tono': 'success' if caja else 'secondary',
        })

    if usuario.rol == Usuario.Rol.ADMINISTRADOR:
        total_hoy = VentaDetalle.objects.filter(
            venta__estado=Venta.Estado.COMPLETADA, venta__fecha__date=hoy,
        ).aggregate(total=Sum(F('cantidad') * F('precio_unitario')))['total'] or 0
        indicadores.append({
            'etiqueta': 'Ventas de hoy', 'valor': f'${total_hoy}', 'detalle': 'Solo ventas completadas', 'tono': 'primary',
        })

    if usuario.has_perm('inventario.view_stock'):
        criticos = (
            Producto.objects.filter(activo=True)
            .annotate(stock_actual=Coalesce(Sum('lotes__stocks__cantidad'), 0))
            .filter(stock_actual__lte=F('stock_minimo'))
            .count()
        )
        indicadores.append({
            'etiqueta': 'Stock crítico', 'valor': criticos,
            'detalle': 'Productos en o bajo el mínimo', 'tono': 'danger' if criticos else 'secondary',
        })

        por_vencer = (
            Lote.objects
            .annotate(stock_actual=Coalesce(Sum('stocks__cantidad'), 0))
            .filter(fecha_vencimiento__lte=hoy + timedelta(days=DIAS_ALERTA_VENCIMIENTO), stock_actual__gt=0)
            .count()
        )
        indicadores.append({
            'etiqueta': 'Por vencer', 'valor': por_vencer,
            'detalle': f'Lotes con stock en {DIAS_ALERTA_VENCIMIENTO} días', 'tono': 'warning' if por_vencer else 'secondary',
        })

    if usuario.has_perm('recetas.view_receta'):
        con_saldo = RecetaDetalle.objects.filter(
            cantidad_dispensada__lt=F('cantidad_prescrita'),
            receta__fecha_emision__lte=hoy, receta__fecha_vencimiento__gte=hoy,
        ).count()
        indicadores.append({
            'etiqueta': 'Recetas con saldo', 'valor': con_saldo,
            'detalle': 'Vigentes, pendientes de dispensar', 'tono': 'secondary',
        })

    return indicadores


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = 'panel/inicio.html'

    def get_context_data(self, **kwargs):
        import json
        from apps.reportes.services import ventas_por_dia
        labels, montos = ventas_por_dia(7)
        return {
            **super().get_context_data(**kwargs),
            'modulos':        _modulos_visibles(self.request.user),
            'indicadores':    _indicadores(self.request.user),
            'chart_7d_labels': json.dumps(labels),
            'chart_7d_montos': json.dumps(montos),
        }

import os
import json
from google import genai
from django.http import JsonResponse
from django.views import View

from apps.panel.models import ChatMensaje

def consultar_disponibilidad(mensaje):
    palabras = re.findall(r'\w+', mensaje.casefold())
    consulta_stock = any(p in {'stock', 'disponible', 'disponibles', 'disponibilidad', 'quedan',
                               'tienen', 'hay', 'precio', 'bodega', 'vitrina'} for p in palabras)
    ignorar = set('cuanto cuánto cuantos cuántos queda quedan disponible disponibles disponibilidad stock hay tienen precio vale para con del las los una por bodega vitrina farmacia unidades producto productos medicamento medicamentos consulta consultar favor necesito quiero saber tienes buscar dame muestra dime hola que qué cuál cual'.split())
    terminos = [p for p in palabras if len(p) >= 3 and p not in ignorar]
    filtro = Q(nombre__iexact=mensaje.strip()) | Q(codigo_barras=mensaje.strip())
    if terminos and (consulta_stock or len(palabras) == len(terminos)):
        coincidencia = Q()
        for termino in terminos:
            coincidencia &= Q(nombre__icontains=termino) | Q(codigo_barras=termino)
        filtro |= coincidencia
    if filtro:
        vigentes = Q(lotes__fecha_vencimiento__gte=timezone.localdate())
        productos = Producto.objects.filter(filtro, activo=True).annotate(
            vitrina=Sum('lotes__stocks__cantidad', filter=vigentes & Q(lotes__stocks__ubicacion=Ubicacion.VITRINA), default=0),
            bodega=Sum('lotes__stocks__cantidad', filter=vigentes & Q(lotes__stocks__ubicacion=Ubicacion.BODEGA), default=0),
        ).order_by('nombre', 'pk')
        filas = list(productos[:11])
        if filas:
            respuesta = [f'{p.nombre}: {p.vitrina} en vitrina, {p.bodega} en bodega. Precio: ${p.precio_venta}.' for p in filas[:10]]
            if len(filas) > 10:
                respuesta.append('Hay más coincidencias. Indica el código de barras para precisar.')
            return '\n'.join(respuesta)
    if consulta_stock:
        return 'Indica el nombre del catálogo o el código de barras para consultar el stock vigente.'


class ChatbotApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        historial = ChatMensaje.objects.filter(usuario=request.user).order_by('fecha')[:50]
        data = [
            {
                'mensaje_usuario': msg.mensaje_usuario,
                'respuesta_bot': msg.respuesta_bot,
                'fecha': msg.fecha.strftime('%d/%m/%Y %H:%M')
            }
            for msg in historial
        ]
        return JsonResponse({'historial': data})

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            disponibilidad = consultar_disponibilidad(user_message)
            if disponibilidad:
                ChatMensaje.objects.create(usuario=request.user, mensaje_usuario=user_message, respuesta_bot=disponibilidad)
                return JsonResponse({'reply': disponibilidad})
            
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                return JsonResponse({'reply': 'Error: La API Key de Gemini no está configurada en el archivo .env.'})
                
            client = genai.Client(api_key=api_key)
            
            # Prompt context (System Instructions)
            prompt = (
                "Eres el asistente virtual experto de 'Farmacia Privada'. "
                "Tu ÚNICO propósito es responder preguntas sobre farmacia, medicamentos, salud, inventario o el sistema. "
                "Si el usuario pregunta sobre CUALQUIER otro tema (recetas de cocina, deportes, etc.), "
                "DEBES negarte amablemente a responder diciendo que solo puedes asistir en temas de farmacia. "
                "Para existencias y precios pide el nombre de catálogo o código de barras. No estimes cantidades ni precios. "
                "Responde de manera profesional y muy breve (máximo 2 oraciones) a la siguiente consulta: "
                f"{user_message}"
            )
            
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            
            # Guardar historial en la base de datos
            ChatMensaje.objects.create(
                usuario=request.user,
                mensaje_usuario=user_message,
                respuesta_bot=response.text
            )
            
            return JsonResponse({'reply': response.text})
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str:
                return JsonResponse({'reply': 'El asistente está recibiendo muchas consultas en este momento debido a alta demanda (503). Por favor, intenta de nuevo en unos segundos.'})
            return JsonResponse({'reply': f'Error en el chatbot: {error_str}'})

class AlertasStockApiView(LoginRequiredMixin, View):
    """Retorna productos con stock crítico para mostrarlos como notificaciones emergentes."""
    def get(self, request, *args, **kwargs):
        # Productos cuyo stock total calculado es <= stock_minimo
        # Dado que el stock se calcula dinámicamente sumando los lotes, debemos anotarlo primero
        productos_criticos = Producto.objects.filter(activo=True).annotate(
            stock_actual=Coalesce(Sum('lotes__stocks__cantidad'), 0)
        ).filter(stock_actual__lte=F('stock_minimo'))[:3]
        
        alertas = [
            {
                'id': p.id,
                'nombre': p.nombre,
                'stock_actual': p.stock_actual,
                'stock_minimo': p.stock_minimo
            }
            for p in productos_criticos
        ]
        
        return JsonResponse({'alertas': alertas})
