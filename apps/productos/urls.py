from django.urls import path

from . import views

app_name = 'productos'

urlpatterns = [
    path('', views.ProductoListView.as_view(), name='lista'),
    path('nuevo/', views.ProductoCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.ProductoUpdateView.as_view(), name='editar'),
    path('<int:pk>/estado/', views.ProductoToggleActivoView.as_view(), name='toggle_activo'),
    path('categorias/', views.CategoriaListView.as_view(), name='categoria_lista'),
    path('categorias/nueva/', views.CategoriaCreateView.as_view(), name='categoria_crear'),
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_editar'),
]
