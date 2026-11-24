from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import UsuarioAdminForm
from .models import CodigoVerificacion, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioAdminForm
    fieldsets = UserAdmin.fieldsets + (
        ('Datos de farmacia', {'fields': ('rut', 'telefono', 'rol')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos de farmacia', {'fields': ('email', 'rut', 'telefono', 'rol')}),
    )
    list_display = ('username', 'first_name', 'last_name', 'rol', 'is_active', 'is_staff')
    list_filter = ('rol', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'rut', 'email')


@admin.register(CodigoVerificacion)
class CodigoVerificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'codigo', 'creado', 'usado')
    readonly_fields = ('usuario', 'codigo', 'creado', 'usado')
    list_filter = ('usado',)

    def has_add_permission(self, request):
        return False
