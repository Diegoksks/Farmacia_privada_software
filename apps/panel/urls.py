from django.urls import path

from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
    path('chatbot/api/', views.ChatbotApiView.as_view(), name='chatbot_api'),
    path('api/alertas-stock/', views.AlertasStockApiView.as_view(), name='alertas_stock_api'),
]
