from django.contrib import admin

from .models import ClienteConvenio, Convenio, ConvenioCobertura


class ConvenioCoberturaInline(admin.TabularInline):
    model = ConvenioCobertura
    extra = 1


@admin.register(Convenio)
class ConvenioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'descuento_porcentaje', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre',)
    inlines = [ConvenioCoberturaInline]


@admin.register(ClienteConvenio)
class ClienteConvenioAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'convenio', 'numero_afiliado', 'vigente_desde', 'vigente_hasta')
    list_filter = ('convenio',)
    search_fields = ('cliente__rut', 'cliente__nombres', 'cliente__apellidos', 'numero_afiliado')
