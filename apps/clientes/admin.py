from django.contrib import admin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'rut', 'telefono', 'email', 'activo')
    search_fields = ('rut', 'nombres', 'apellidos')
    list_filter = ('activo',)
