from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from .models import Categoria, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'tipo', 'nivel_control', 'precio_venta', 'stock_actual', 'activo')
    list_filter = ('tipo', 'nivel_control', 'categoria', 'activo')
    search_fields = ('nombre', 'principio_activo', 'codigo_barras', 'laboratorio')

    @admin.display(description='Stock actual')
    def stock_actual(self, obj):
        total = obj.lotes.aggregate(total=Sum('stocks__cantidad'))['total'] or 0
        if total <= obj.stock_minimo:
            return format_html('<span style="color: #dc3545; font-weight: bold;">{} (crítico)</span>', total)
        return total
