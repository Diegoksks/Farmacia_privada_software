from django.urls import path

from . import views

app_name = 'convenios'

urlpatterns = [
    path('', views.ConvenioListView.as_view(), name='lista'),
    path('nuevo/', views.ConvenioCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.ConvenioDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.ConvenioUpdateView.as_view(), name='editar'),
    path('afiliaciones/', views.ClienteConvenioListView.as_view(), name='afiliaciones_lista'),
]
