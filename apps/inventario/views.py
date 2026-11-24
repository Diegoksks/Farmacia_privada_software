import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseRedirect
from django.views.generic import FormView, ListView, DetailView, CreateView, UpdateView, View
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.db import transaction
from django.conf import settings
from google import genai

from django.utils import timezone
from datetime import timedelta
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

from apps.ventas.models import VentaDetalle
from apps.productos.models import Producto

from . import services
from .models import Lote, OrdenCompra, MovimientoStock, Proveedor
from .forms import AjusteStockForm, TraspasoStockForm, OrdenCompraForm, OrdenCompraDetalleFormSet, ProveedorForm



class TraspasoStockView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = 'inventario/traspaso.html'
    form_class = TraspasoStockForm
    permission_required = 'inventario.view_lote'
    success_url = reverse_lazy('inventario:traspaso')

    def form_valid(self, form):
        try:
            services.traspasar_stock(
                lote=form.cleaned_data['lote'],
                cantidad=form.cleaned_data['cantidad'],
                usuario=self.request.user,
                observacion=form.cleaned_data['observacion'],
            )
        except ValueError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        messages.success(self.request, 'Traspaso a vitrina registrado correctamente.')
        return super().form_valid(form)


class AjusteStockView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = 'inventario/ajuste.html'
    form_class = AjusteStockForm
    permission_required = 'inventario.add_movimientostock'
    success_url = reverse_lazy('inventario:ajuste')

    def form_valid(self, form):
        try:
            services.registrar_ajuste(
                lote=form.cleaned_data['lote'],
                ubicacion=form.cleaned_data['ubicacion'],
                cantidad_delta=form.cleaned_data['cantidad_delta'],
                usuario=self.request.user,
                motivo=form.cleaned_data['motivo'],
            )
        except ValueError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        messages.success(self.request, 'Ajuste de stock registrado correctamente.')
        return super().form_valid(form)


class LoteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Listado de Lotes con su stock en Bodega y Vitrina."""
    model = Lote
    template_name = 'inventario/lote_lista.html'
    permission_required = 'inventario.view_lote'
    context_object_name = 'lotes'
    paginate_by = 30

    def get_queryset(self):
        qs = Lote.objects.select_related('producto').annotate(
            stock_bodega=Coalesce(Sum('stocks__cantidad', filter=Q(stocks__ubicacion='BODEGA')), 0),
            stock_vitrina=Coalesce(Sum('stocks__cantidad', filter=Q(stocks__ubicacion='VITRINA')), 0),
            total_stock=Coalesce(Sum('stocks__cantidad'), 0)
        )

        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(producto__nombre__icontains=busqueda) | 
                Q(numero_lote__icontains=busqueda)
            )

        estado = self.request.GET.get('estado')
        if estado == 'vencidos':
            from django.utils import timezone
            hoy = timezone.localdate()
            qs = qs.filter(fecha_vencimiento__lt=hoy)
        elif estado == 'con_stock':
            qs = qs.filter(total_stock__gt=0)
            
        return qs.order_by('fecha_vencimiento')

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'filtros': self.request.GET}


class OrdenCompraListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Listado de órdenes de compra."""
    model = OrdenCompra
    template_name = 'inventario/orden_lista.html'
    permission_required = 'inventario.view_ordencompra'
    context_object_name = 'ordenes'
    paginate_by = 20

    def get_queryset(self):
        qs = OrdenCompra.objects.select_related('proveedor', 'creado_por').order_by('-creado_en')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(proveedor__nombre__icontains=q) |
                Q(proveedor__rut__icontains=q) |
                Q(numero_factura__icontains=q)
            )
        return qs
        
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'filtros': self.request.GET}


class OrdenCompraDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Detalle de una orden de compra."""
    model = OrdenCompra
    template_name = 'inventario/orden_detalle.html'
    permission_required = 'inventario.view_ordencompra'
    context_object_name = 'orden'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detalles'] = self.object.detalles.select_related('producto')
        return context


class MovimientoStockListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Kardex: Historial inmutable de movimientos de stock."""
    model = MovimientoStock
    template_name = 'inventario/movimiento_lista.html'
    permission_required = 'inventario.view_movimientostock'
    context_object_name = 'movimientos'
    paginate_by = 30

    def get_queryset(self):
        qs = MovimientoStock.objects.select_related('lote__producto', 'usuario').order_by('-fecha')
        
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(lote__producto__nombre__icontains=busqueda) | 
                Q(lote__numero_lote__icontains=busqueda)
            )

        tipo = self.request.GET.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)
            
        return qs

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'filtros': self.request.GET,
            'tipos_movimiento': MovimientoStock.Tipo.choices,
        }


class OrdenCompraCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = OrdenCompra
    form_class = OrdenCompraForm
    template_name = 'inventario/orden_form.html'
    permission_required = 'inventario.add_ordencompra'
    
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['detalles'] = OrdenCompraDetalleFormSet(self.request.POST)
        else:
            data['detalles'] = OrdenCompraDetalleFormSet()
        
        # Mapa de datos de proveedores para previsualización instantánea
        provs = Proveedor.objects.filter(activo=True)
        provs_map = {}
        for p in provs:
            provs_map[str(p.id)] = {
                'id': p.id,
                'nombre': p.nombre,
                'rut': p.rut or 'Sin RUT',
                'giro': p.giro or '—',
                'contacto': p.contacto_nombre or '—',
                'telefono': p.telefono or '—',
                'email': p.email or '—',
                'direccion': f"{p.direccion}, {p.ciudad}" if p.direccion else (p.ciudad or '—'),
                'notas': p.notas or '',
            }
        data['proveedores_json'] = json.dumps(provs_map)
        data['proveedor_form'] = ProveedorForm()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        detalles = context['detalles']
        if form.is_valid() and detalles.is_valid():
            with transaction.atomic():
                form.instance.creado_por = self.request.user
                self.object = form.save()
                detalles.instance = self.object
                detalles.save()
            messages.success(self.request, f'Orden de compra #{self.object.pk:04d} registrada exitosamente.')
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))
            
    def get_success_url(self):
        return reverse_lazy('inventario:orden_detalle', kwargs={'pk': self.object.pk})


class OrdenCompraRecibirView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'inventario.change_ordencompra'

    def post(self, request, pk):
        orden = get_object_or_404(OrdenCompra, pk=pk)
        try:
            services.recibir_orden_compra(orden, request.user, request.POST)
            messages.success(request, f'Orden #{orden.pk:04d} recibida correctamente. Lotes y stock ingresados a bodega.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('inventario:orden_detalle', pk=orden.pk)


class ProveedorListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Proveedor
    template_name = 'inventario/proveedor_lista.html'
    context_object_name = 'proveedores'
    permission_required = 'inventario.view_ordencompra'
    paginate_by = 15

    def get_queryset(self):
        qs = Proveedor.objects.all().order_by('nombre')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) |
                Q(rut__icontains=q) |
                Q(contacto_nombre__icontains=q) |
                Q(email__icontains=q)
            )
        estado = self.request.GET.get('estado')
        if estado == 'activos':
            qs = qs.filter(activo=True)
        elif estado == 'inactivos':
            qs = qs.filter(activo=False)
        return qs

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'filtros': self.request.GET}


class ProveedorCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Proveedor
    form_class = ProveedorForm
    template_name = 'inventario/proveedor_form.html'
    permission_required = 'inventario.add_ordencompra'
    success_url = reverse_lazy('inventario:proveedor_lista')

    def form_valid(self, form):
        messages.success(self.request, f'Proveedor "{form.instance.nombre}" creado exitosamente.')
        return super().form_valid(form)


class ProveedorUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Proveedor
    form_class = ProveedorForm
    template_name = 'inventario/proveedor_form.html'
    permission_required = 'inventario.change_ordencompra'
    success_url = reverse_lazy('inventario:proveedor_lista')

    def form_valid(self, form):
        messages.success(self.request, f'Proveedor "{form.instance.nombre}" actualizado exitosamente.')
        return super().form_valid(form)


class ProveedorCreateApiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """API para crear proveedor rápidamente desde el modal de orden_form."""
    permission_required = 'inventario.add_ordencompra'

    def post(self, request):
        form = ProveedorForm(request.POST)
        if form.is_valid():
            prov = form.save()
            return JsonResponse({
                'success': True,
                'proveedor': {
                    'id': prov.id,
                    'nombre': prov.nombre,
                    'rut': prov.rut or 'Sin RUT',
                    'giro': prov.giro or '—',
                    'contacto': prov.contacto_nombre or '—',
                    'telefono': prov.telefono or '—',
                    'email': prov.email or '—',
                    'direccion': f"{prov.direccion}, {prov.ciudad}" if prov.direccion else (prov.ciudad or '—'),
                    'notas': prov.notas or '',
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data()
            }, status=400)


class ProyeccionDemandaView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'inventario/proyeccion_demanda.html'
    context_object_name = 'proyecciones'
    permission_required = 'inventario.view_movimientostock'

    def get_queryset(self):
        hoy = timezone.localdate()
        hace_30_dias = hoy - timedelta(days=30)
        
        # Obtener ventas de los últimos 30 días
        ventas = VentaDetalle.objects.filter(
            venta__fecha__date__gte=hace_30_dias,
            venta__estado='COMPLETADA'
        ).values('producto_id', 'producto__nombre').annotate(
            total_vendido=Sum('cantidad')
        )
        
        if not ventas:
            return []
            
        # Volver a consultar pero por fecha para armar el dataframe
        ventas_diarias_qs = VentaDetalle.objects.filter(
            venta__fecha__date__gte=hace_30_dias,
            venta__estado='COMPLETADA'
        ).values('producto_id', 'venta__fecha__date').annotate(
            total_vendido=Sum('cantidad')
        )
        
        if not ventas_diarias_qs:
            return []
            
        df = pd.DataFrame(ventas_diarias_qs)
        df['fecha'] = pd.to_datetime(df['venta__fecha__date'])
        
        proyecciones = []
        productos = Producto.objects.filter(id__in=df['producto_id'].unique()).annotate(
            stock_total=Coalesce(Sum('lotes__stocks__cantidad'), 0)
        )
        
        # Rango de fechas completo para el modelo
        idx = pd.date_range(hace_30_dias, hoy)
        
        for producto in productos:
            df_prod = df[df['producto_id'] == producto.id].copy()
            if df_prod.empty:
                continue
                
            ventas_diarias = df_prod.groupby('fecha')['total_vendido'].sum().reset_index()
            ventas_diarias.set_index('fecha', inplace=True)
            ventas_diarias = ventas_diarias.reindex(idx, fill_value=0).reset_index()
            ventas_diarias.columns = ['fecha', 'total_vendido']
            
            # Linear Regression for trend
            X = np.arange(len(ventas_diarias)).reshape(-1, 1)
            y = ventas_diarias['total_vendido'].values
            
            modelo = LinearRegression()
            modelo.fit(X, y)
            
            # Predict for the next day
            prediccion_diaria = modelo.predict([[len(ventas_diarias)]])[0]
            
            if prediccion_diaria < 0.1:
                prediccion_diaria = ventas_diarias['total_vendido'].mean()
                
            if prediccion_diaria <= 0:
                dias_restantes = 999
            else:
                dias_restantes = int(producto.stock_total / prediccion_diaria)
                
            estado = 'crítico' if dias_restantes <= 7 else 'alerta' if dias_restantes <= 15 else 'normal'
                
            proyecciones.append({
                'producto': producto,
                'stock_actual': producto.stock_total,
                'promedio_diario': round(prediccion_diaria, 2),
                'dias_restantes': dias_restantes,
                'estado': estado
            })
            
        proyecciones.sort(key=lambda x: x['dias_restantes'])
        return proyecciones


class ProyeccionDemandaIAApiView(LoginRequiredMixin, View):
    """Toma las proyecciones matemáticas y usa Gemini para generar un reporte ejecutivo."""
    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        try:
            # Reutilizamos la lógica matemática de la vista original
            vista_base = ProyeccionDemandaView()
            vista_base.request = request
            proyecciones = vista_base.get_queryset()
            
            if not proyecciones:
                return JsonResponse({'reporte': 'No hay datos de ventas suficientes para que la IA los analice.'})
                
            # Preparar contexto para Gemini
            contexto = "Datos de inventario y proyecciones (Scikit-Learn):\n"
            for p in proyecciones[:20]:  # Limitar a los 20 más críticos
                contexto += f"- Producto: {p['producto'].nombre} | Stock: {p['stock_actual']} | Venta Diaria Promedio: {p['promedio_diario']} | Días Restantes: {p['dias_restantes']} | Estado: {p['estado']}\n"
                
            prompt = (
                "Eres el Analista Comercial de 'Farmacia Privada'. Tienes acceso a las proyecciones de demanda calculadas matemáticamente. "
                "Tu objetivo es escribir un REPORTE EJECUTIVO BREVE (máximo 3 párrafos cortos) para el Administrador. "
                "1. Resume qué productos están en estado crítico y deben reponerse URGENTE. "
                "2. Da un consejo rápido sobre cuántas unidades pedir basado en su venta diaria. "
                "Usa un tono profesional, directo, y formatea tu respuesta en HTML ligero (puedes usar <b>, <ul>, <li>). "
                "Aquí están los datos:\n\n"
                f"{contexto}"
            )
            
            import os
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                return JsonResponse({'reporte': 'Error: La API Key de Gemini no está configurada.'})
                
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            
            return JsonResponse({'reporte': response.text})
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str:
                return JsonResponse({'reporte': 'El motor de IA está recibiendo muchas consultas en este momento debido a alta demanda (503). Por favor, intenta de nuevo en unos segundos.'})
            return JsonResponse({'reporte': f'Error conectando con la IA: {error_str}'})
