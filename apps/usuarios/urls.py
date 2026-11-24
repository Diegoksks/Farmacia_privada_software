from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'usuarios'

urlpatterns = [
    path('login/', views.LoginConDobleFactorView.as_view(), name='login'),
    path('verificar/', views.VerificarCodigoView.as_view(), name='verificar_codigo'),
    path('logout/', LogoutView.as_view(next_page='usuarios:login'), name='logout'),
    path('cambiar-contrasena/', views.cambiar_contrasena, name='cambiar_contrasena'),
    
    # Nuevas rutas para frontend
    path('', views.UsuarioListView.as_view(), name='lista'),
    path('nuevo/', views.UsuarioCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='editar'),
    path('roles/', views.GrupoListView.as_view(), name='grupo_lista'),
]
