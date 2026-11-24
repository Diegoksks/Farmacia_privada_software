from django.contrib import admin
from django.utils.html import format_html

from .models import DispensacionReceta, LibroControl, Receta, RecetaDetalle


class RecetaDetalleInline(admin.TabularInline):
    model = RecetaDetalle
    extra = 1
    readonly_fields = ('cantidad_dispensada',)


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'medico_nombre', 'tipo', 'fecha_emision', 'fecha_vencimiento', 'vigencia')
    list_filter = ('tipo',)
    search_fields = ('cliente__rut', 'cliente__nombres', 'cliente__apellidos', 'medico_rut', 'medico_nombre', 'folio')
    inlines = [RecetaDetalleInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Vigencia')
    def vigencia(self, obj):
        if obj.esta_vigente:
            return format_html('<span style="color: #198754; font-weight: bold;">{}</span>', 'Vigente')
        return format_html('<span style="color: #dc3545; font-weight: bold;">{}</span>', 'Vencida')


@admin.register(DispensacionReceta)
class DispensacionRecetaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'detalle', 'cantidad', 'retirado_por', 'usuario', 'observacion')
    list_filter = ('detalle__producto__nivel_control',)
    search_fields = ('detalle__producto__nombre', 'detalle__receta__cliente__rut')
    date_hierarchy = 'fecha'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LibroControl)
class LibroControlAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'detalle', 'cantidad', 'retirado_por', 'usuario', 'observacion')
    list_filter = ('detalle__producto__categoria_regulatoria',)
    search_fields = ('detalle__producto__nombre', 'detalle__receta__cliente__rut')
    date_hierarchy = 'fecha'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
