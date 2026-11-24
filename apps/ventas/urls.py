from django.urls import path

from . import views

app_name = 'ventas'

urlpatterns = [
    path('caja/abrir/', views.AbrirCajaView.as_view(), name='abrir_caja'),
    path('caja/cerrar/', views.CerrarCajaView.as_view(), name='cerrar_caja'),
    path('pos/', views.PuntoVentaView.as_view(), name='punto_venta'),
    path('pos/agregar-codigo/', views.AgregarPorCodigoBarrasView.as_view(), name='agregar_codigo'),
    path('pos/agregar-receta/', views.AgregarPorRecetaView.as_view(), name='agregar_receta'),
    path('pos/quitar/<int:index>/', views.QuitarLineaView.as_view(), name='quitar_linea'),
    path('pos/cantidad/<int:index>/', views.ActualizarCantidadView.as_view(), name='actualizar_cantidad'),
    path('pos/finalizar/', views.FinalizarVentaView.as_view(), name='finalizar_venta'),
    
    # API endpoints for POS
    path('pos/api/productos/', views.BuscarProductoAjaxView.as_view(), name='api_buscar_producto'),
    path('pos/api/clientes/crear/', views.CrearClienteAjaxView.as_view(), name='api_crear_cliente'),
    
    # Historial de Ventas y Cajas
    path('historial/', views.VentaListView.as_view(), name='venta_lista'),
    path('historial/cajas/', views.CajaListView.as_view(), name='caja_lista'),
    path('historial/documentos/', views.DocumentoTributarioListView.as_view(), name='documento_lista'),
    
    path('<int:pk>/', views.DetalleVentaView.as_view(), name='detalle_venta'),
    path('<int:pk>/imprimir/', views.ImprimirDocumentoView.as_view(), name='imprimir_documento'),
    path('<int:pk>/anular/', views.AnularVentaView.as_view(), name='anular_venta'),
]
