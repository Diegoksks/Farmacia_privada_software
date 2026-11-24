from django.contrib import admin, messages
from django.utils.html import format_html

from . import services
from .models import Lote, MovimientoStock, OrdenCompra, OrdenCompraDetalle, Stock, Proveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'contacto_nombre', 'telefono', 'email', 'ciudad', 'activo')
    list_filter = ('activo', 'ciudad')
    search_fields = ('nombre', 'rut', 'contacto_nombre', 'email')


class StockInline(admin.TabularInline):
    model = Stock
    extra = 0
    can_delete = False
    readonly_fields = ('ubicacion', 'cantidad')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ('producto', 'numero_lote', 'fecha_vencimiento', 'alerta_vencimiento', 'stock_total')
    list_filter = ('producto__categoria',)
    search_fields = ('numero_lote', 'producto__nombre')
    inlines = [StockInline]

    @admin.display(description='Vencimiento')
    def alerta_vencimiento(self, obj):
        dias = obj.dias_para_vencer
        if dias < 0:
            color, texto = '#dc3545', f'Vencido hace {abs(dias)} días'
        elif dias <= 90:
            color, texto = '#fd7e14', f'Vence en {dias} días'
        else:
            color, texto = '#198754', f'Vence en {dias} días'
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, texto)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('lote', 'ubicacion', 'cantidad')
    list_filter = ('ubicacion',)
    search_fields = ('lote__numero_lote', 'lote__producto__nombre')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'lote', 'cantidad', 'ubicacion_origen', 'ubicacion_destino', 'usuario')
    list_filter = ('tipo',)
    search_fields = ('lote__numero_lote', 'lote__producto__nombre', 'observacion')
    date_hierarchy = 'fecha'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrdenCompraDetalleInline(admin.TabularInline):
    model = OrdenCompraDetalle
    extra = 1


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'proveedor', 'numero_factura', 'estado', 'creado_por', 'creado_en', 'recibido_en')
    list_filter = ('estado',)
    search_fields = ('proveedor__nombre', 'proveedor__rut', 'numero_factura')
    inlines = [OrdenCompraDetalleInline]
    actions = ['marcar_como_recibida']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.estado != OrdenCompra.Estado.PENDIENTE:
            return ('proveedor', 'estado', 'creado_por')
        return ()

    @admin.action(description='Marcar como recibida (genera lotes y stock en bodega)')
    def marcar_como_recibida(self, request, queryset):
        for orden in queryset:
            try:
                services.recibir_orden_compra(orden, request.user)
            except ValueError as error:
                self.message_user(request, f'{orden}: {error}', level=messages.ERROR)
            else:
                self.message_user(request, f'{orden} recibida correctamente.', level=messages.SUCCESS)
