from django.contrib import admin

from .models import Caja, DocumentoTributario, Venta, VentaDetalle


class SoloLecturaAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Caja)
class CajaAdmin(SoloLecturaAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'usuario', 'monto_apertura', 'fecha_apertura', 'esta_abierta', 'monto_cierre_declarado', 'diferencia')
    list_filter = ('usuario',)
    date_hierarchy = 'fecha_apertura'


class VentaDetalleInline(admin.TabularInline):
    model = VentaDetalle
    extra = 0
    can_delete = False
    readonly_fields = ('producto', 'cantidad', 'precio_lista', 'precio_unitario', 'convenio', 'receta_detalle')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Venta)
class VentaAdmin(SoloLecturaAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'fecha', 'cliente', 'vendedor', 'metodo_pago', 'estado', 'total')
    list_filter = ('estado', 'metodo_pago')
    search_fields = ('id', 'cliente__rut', 'cliente__nombres', 'cliente__apellidos')
    date_hierarchy = 'fecha'
    inlines = [VentaDetalleInline]


@admin.register(DocumentoTributario)
class DocumentoTributarioAdmin(SoloLecturaAdminMixin, admin.ModelAdmin):
    list_display = ('tipo', 'folio', 'venta', 'fecha_emision')
    list_filter = ('tipo',)
    date_hierarchy = 'fecha_emision'
