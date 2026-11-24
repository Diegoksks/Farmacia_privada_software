import io
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView
from openpyxl import Workbook

from apps.comun.pdf import render_pdf_response
from apps.usuarios.models import Usuario

from . import services


class SoloAdministradorMixin(UserPassesTestMixin):
    """Los indicadores comerciales globales son responsabilidad del
    Administrador; no son parte de la operación diaria de los demás roles."""

    def test_func(self):
        return self.request.user.rol == Usuario.Rol.ADMINISTRADOR


class DashboardView(LoginRequiredMixin, SoloAdministradorMixin, TemplateView):
    template_name = 'reportes/dashboard.html'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **services.resumen_dashboard()}


def _leer_rango(request):
    hoy = timezone.localdate()
    desde = request.GET.get('desde')
    hasta = request.GET.get('hasta')
    desde = date.fromisoformat(desde) if desde else hoy.replace(day=1)
    hasta = date.fromisoformat(hasta) if hasta else hoy
    return desde, hasta


def _excel_response(titulo_hoja, encabezados, filas, nombre_archivo):
    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo_hoja
    hoja.append(encabezados)
    for fila in filas:
        hoja.append(fila)
    buffer = io.BytesIO()
    libro.save(buffer)
    response = HttpResponse(
        buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}.xlsx"'
    return response


class ReporteVentasView(LoginRequiredMixin, SoloAdministradorMixin, TemplateView):
    template_name = 'reportes/reporte_ventas.html'

    def get(self, request, *args, **kwargs):
        desde, hasta = _leer_rango(request)
        detalles = list(services.dataset_ventas(desde, hasta))
        total = sum(detalle.subtotal for detalle in detalles)

        formato = request.GET.get('formato')
        if formato == 'pdf':
            return render_pdf_response(
                'reportes/pdf_ventas.html', {'desde': desde, 'hasta': hasta, 'detalles': detalles, 'total': total},
                f'ventas_{desde}_{hasta}',
            )
        if formato == 'excel':
            filas = [
                [
                    d.venta.fecha.strftime('%d-%m-%Y %H:%M'), d.venta.pk,
                    d.venta.cliente.nombre_completo if d.venta.cliente else '',
                    d.producto.nombre, d.cantidad, d.precio_unitario, d.subtotal,
                ]
                for d in detalles
            ]
            return _excel_response(
                'Ventas', ['Fecha', 'Venta', 'Cliente', 'Producto', 'Cantidad', 'Precio unitario', 'Subtotal'],
                filas, f'ventas_{desde}_{hasta}',
            )

        return self.render_to_response({'desde': desde, 'hasta': hasta, 'detalles': detalles, 'total': total})


class ReporteInventarioView(LoginRequiredMixin, SoloAdministradorMixin, TemplateView):
    template_name = 'reportes/reporte_inventario.html'

    def get(self, request, *args, **kwargs):
        productos = list(services.dataset_inventario())

        formato = request.GET.get('formato')
        if formato == 'pdf':
            return render_pdf_response('reportes/pdf_inventario.html', {'productos': productos}, 'inventario')
        if formato == 'excel':
            filas = [
                [p.nombre, p.categoria.nombre, p.stock_actual, p.stock_minimo, p.precio_venta]
                for p in productos
            ]
            return _excel_response(
                'Inventario', ['Producto', 'Categoría', 'Stock actual', 'Stock mínimo', 'Precio venta'],
                filas, 'inventario',
            )

        return self.render_to_response({'productos': productos})
