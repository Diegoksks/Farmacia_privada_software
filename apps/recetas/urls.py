from django.urls import path

from . import views

app_name = 'recetas'

urlpatterns = [
    path('', views.RecetaListView.as_view(), name='lista'),
    path('nueva/', views.RecetaCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.RecetaDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.RecetaUpdateView.as_view(), name='editar'),
    
    path('dispensaciones/', views.DispensacionListView.as_view(), name='dispensacion_lista'),
    path('libro-control/', views.LibroControlListView.as_view(), name='libro_control'),
    
    path('recordatorios/', views.RecordatoriosListView.as_view(), name='recordatorios_lista'),
    path('api/enviar-recordatorios/', views.EnviarRecordatoriosApiView.as_view(), name='enviar_recordatorios_api'),
]
