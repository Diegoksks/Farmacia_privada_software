from django.urls import path

from . import views

app_name = 'inventario'

urlpatterns = [
    path('traspaso/', views.TraspasoStockView.as_view(), name='traspaso'),
    path('ajuste/', views.AjusteStockView.as_view(), name='ajuste'),
    
    # Lotes y Órdenes
    path('lotes/', views.LoteListView.as_view(), name='lote_lista'),
    path('ordenes/', views.OrdenCompraListView.as_view(), name='orden_lista'),
    path('ordenes/nueva/', views.OrdenCompraCreateView.as_view(), name='orden_crear'),
    path('ordenes/<int:pk>/', views.OrdenCompraDetailView.as_view(), name='orden_detalle'),
    path('ordenes/<int:pk>/recibir/', views.OrdenCompraRecibirView.as_view(), name='orden_recibir'),
    path('movimientos/', views.MovimientoStockListView.as_view(), name='movimiento_lista'),
    path('proyeccion/', views.ProyeccionDemandaView.as_view(), name='proyeccion_demanda'),
    path('proyeccion/ia/api/', views.ProyeccionDemandaIAApiView.as_view(), name='proyeccion_ia_api'),

    # Proveedores
    path('proveedores/', views.ProveedorListView.as_view(), name='proveedor_lista'),
    path('proveedores/nuevo/', views.ProveedorCreateView.as_view(), name='proveedor_crear'),
    path('proveedores/<int:pk>/editar/', views.ProveedorUpdateView.as_view(), name='proveedor_editar'),
    path('api/proveedores/crear/', views.ProveedorCreateApiView.as_view(), name='proveedor_api_crear'),
]
