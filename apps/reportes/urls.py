from django.urls import path

from . import views

app_name = 'reportes'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('ventas/', views.ReporteVentasView.as_view(), name='reporte_ventas'),
    path('inventario/', views.ReporteInventarioView.as_view(), name='reporte_inventario'),
]
