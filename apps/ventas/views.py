from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, FormView, ListView
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce

from apps.comun.pdf import render_pdf_response
from apps.productos.models import Producto
from apps.recetas.models import RecetaDetalle
from apps.clientes.models import Cliente
from apps.clientes.forms import ClienteForm

from . import services
from .forms import AbrirCajaForm, AgregarPorCodigoBarrasForm, AgregarPorRecetaForm, AnularVentaForm, CerrarCajaForm, FinalizarVentaForm
from .models import Caja, DocumentoTributario, Venta

CARRITO_SESSION_KEY = 'carrito_venta'


def _get_carrito(session):
    return session.setdefault(CARRITO_SESSION_KEY, [])


def _guardar_carrito(session, carrito):
    session[CARRITO_SESSION_KEY] = carrito
    session.modified = True


def _resolver_carrito(carrito):
    lineas = []
    total = 0
    for indice, item in enumerate(carrito):
        producto = Producto.objects.get(pk=item['producto_id'])
        cantidad = item['cantidad']
        subtotal = producto.precio_venta * cantidad
        receta_detalle = None
        if item.get('receta_detalle_id'):
            receta_detalle = RecetaDetalle.objects.select_related('receta__cliente').get(pk=item['receta_detalle_id'])
        lineas.append({
            'index': indice, 'producto': producto, 'cantidad': cantidad,
            'subtotal': subtotal, 'receta_detalle': receta_detalle,
            'retirado_por': item.get('retirado_por'),
        })
        total += subtotal
    return lineas, total


def _caja_abierta_de(usuario):
    return Caja.objects.filter(usuario=usuario, fecha_cierre__isnull=True).first()


class AbrirCajaView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = 'ventas/abrir_caja.html'
    form_class = AbrirCajaForm
    permission_required = 'ventas.add_caja'
    success_url = reverse_lazy('ventas:punto_venta')

    def dispatch(self, request, *args, **kwargs):
        if _caja_abierta_de(request.user):
            return redirect('ventas:punto_venta')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        services.abrir_caja(self.request.user, form.cleaned_data['monto_apertura'])
        messages.success(self.request, 'Caja abierta correctamente.')
        return super().form_valid(form)


class CerrarCajaView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = 'ventas/cerrar_caja.html'
    form_class = CerrarCajaForm
    permission_required = 'ventas.change_caja'
    success_url = reverse_lazy('ventas:abrir_caja')

    def dispatch(self, request, *args, **kwargs):
        self.caja = _caja_abierta_de(request.user)
        if not self.caja:
            messages.info(request, 'No tienes una caja abierta.')
            return redirect('ventas:abrir_caja')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        totales = self.caja.ventas.filter(estado='COMPLETADA').values('metodo_pago').annotate(
            total=Sum(F('detalles__cantidad') * F('detalles__precio_unitario'))
        )
        resumen_pagos = {t['metodo_pago']: t['total'] for t in totales}
        total_digital = sum(t['total'] for t in totales if t['metodo_pago'] != 'EFECTIVO')
        total_efectivo = sum(t['total'] for t in totales if t['metodo_pago'] == 'EFECTIVO')
        
        return {
            **super().get_context_data(**kwargs),
            'caja': self.caja,
            'resumen_pagos': resumen_pagos,
            'total_digital': total_digital,
            'total_efectivo': total_efectivo,
        }

    def form_valid(self, form):
        caja = services.cerrar_caja(self.caja, form.cleaned_data['monto_declarado'], self.request.user)
        if caja.diferencia == 0:
            messages.success(self.request, 'Caja cerrada sin descuadre.')
        else:
            messages.warning(self.request, f'Caja cerrada con descuadre de ${caja.diferencia} CLP.')
        return super().form_valid(form)


class PuntoVentaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = 'ventas/punto_venta.html'
    permission_required = 'ventas.add_venta'

    def get(self, request):
        caja = _caja_abierta_de(request.user)
        if not caja:
            messages.info(request, 'Debes abrir caja antes de vender.')
            return redirect('ventas:abrir_caja')

        lineas, total = _resolver_carrito(_get_carrito(request.session))
        context = {
            'caja': caja, 'lineas': lineas, 'total': total,
            'form_barras': AgregarPorCodigoBarrasForm(),
            'form_receta': AgregarPorRecetaForm(),
            'form_finalizar': FinalizarVentaForm(),
        }
        return render(request, self.template_name, context)


class AgregarPorCodigoBarrasView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'ventas.add_venta'

    def post(self, request):
        form = AgregarPorCodigoBarrasForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Cantidad o código de barras inválido.')
            return redirect('ventas:punto_venta')

        try:
            producto = Producto.objects.get(codigo_barras=form.cleaned_data['codigo_barras'], activo=True)
        except Producto.DoesNotExist:
            messages.error(request, 'No se encontró un producto activo con ese código de barras.')
            return redirect('ventas:punto_venta')

        if producto.requiere_receta:
            messages.error(request, f'{producto.nombre} requiere receta; agrégalo desde la sección de recetas.')
            return redirect('ventas:punto_venta')

        carrito = _get_carrito(request.session)
        encontrado = False
        for item in carrito:
            if item['producto_id'] == producto.pk and not item.get('receta_detalle_id'):
                item['cantidad'] += form.cleaned_data['cantidad']
                encontrado = True
                break
        if not encontrado:
            carrito.append({'producto_id': producto.pk, 'cantidad': form.cleaned_data['cantidad'], 'receta_detalle_id': None})
        _guardar_carrito(request.session, carrito)
        messages.success(request, f'{producto.nombre} agregado.')
        return redirect('ventas:punto_venta')


class AgregarPorRecetaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'ventas.add_venta'

    def post(self, request):
        form = AgregarPorRecetaForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Selecciona una receta válida.')
            return redirect('ventas:punto_venta')

        receta_detalle = form.cleaned_data['receta_detalle']
        cantidad = form.cleaned_data['cantidad']
        if cantidad > receta_detalle.saldo:
            messages.error(request, f'Saldo insuficiente: quedan {receta_detalle.saldo} unidades.')
            return redirect('ventas:punto_venta')

        retirado_por = {
            'nombre': form.cleaned_data['retirado_por_nombre'],
            'rut': form.cleaned_data['retirado_por_rut'],
            'relacion': form.cleaned_data['retirado_por_relacion'],
        }
        carrito = _get_carrito(request.session)
        carrito.append({
            'producto_id': receta_detalle.producto_id, 'cantidad': cantidad, 'receta_detalle_id': receta_detalle.pk,
            'retirado_por': retirado_por if retirado_por['nombre'] else None,
        })
        _guardar_carrito(request.session, carrito)
        messages.success(request, f'{receta_detalle.producto.nombre} agregado desde receta.')
        return redirect('ventas:punto_venta')


class QuitarLineaView(LoginRequiredMixin, View):
    def post(self, request, index):
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '')
        )
        carrito = _get_carrito(request.session)
        if 0 <= index < len(carrito):
            carrito.pop(index)
            _guardar_carrito(request.session, carrito)
        
        if is_ajax:
            _, total = _resolver_carrito(carrito)
            return JsonResponse({
                'ok': True,
                'vacio': len(carrito) == 0,
                'total': int(total),
                'total_formateado': f'${round(total)} CLP',
            })
        return redirect('ventas:punto_venta')


class ActualizarCantidadView(LoginRequiredMixin, View):
    """Permite incrementar o decrementar la cantidad de un ítem en el carrito del POS."""
    def post(self, request, index):
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '')
        )
        carrito = _get_carrito(request.session)
        if not (0 <= index < len(carrito)):
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Línea de carrito inválida.'}, status=400)
            messages.error(request, 'Línea de carrito inválida.')
            return redirect('ventas:punto_venta')

        item = carrito[index]
        producto = Producto.objects.filter(pk=item['producto_id'], activo=True).first()
        if not producto:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Producto no encontrado.'}, status=404)
            messages.error(request, 'Producto no encontrado.')
            return redirect('ventas:punto_venta')

        accion = request.POST.get('accion')
        nueva_cantidad = item['cantidad']

        if accion == 'incrementar':
            nueva_cantidad += 1
        elif accion == 'decrementar':
            nueva_cantidad -= 1
        elif 'cantidad' in request.POST:
            try:
                nueva_cantidad = int(request.POST['cantidad'])
            except (ValueError, TypeError):
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': 'Cantidad inválida.'}, status=400)
                messages.error(request, 'Cantidad inválida.')
                return redirect('ventas:punto_venta')

        # Si disminuye a 0 o menos, quitar del carrito
        if nueva_cantidad <= 0:
            carrito.pop(index)
            _guardar_carrito(request.session, carrito)
            if is_ajax:
                _, total = _resolver_carrito(carrito)
                return JsonResponse({
                    'ok': True,
                    'eliminado': True,
                    'vacio': len(carrito) == 0,
                    'total': int(total),
                    'total_formateado': f'${round(total)} CLP',
                })
            messages.info(request, f'{producto.nombre} eliminado del carrito.')
            return redirect('ventas:punto_venta')

        # Validación si proviene de receta médica
        if item.get('receta_detalle_id'):
            receta_detalle = RecetaDetalle.objects.filter(pk=item['receta_detalle_id']).first()
            if receta_detalle and nueva_cantidad > receta_detalle.saldo:
                msg = f'No puedes superar el saldo disponible de la receta para {producto.nombre} ({receta_detalle.saldo} disponibles).'
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': msg}, status=400)
                messages.warning(request, msg)
                return redirect('ventas:punto_venta')

        # Validación de stock en vitrina
        from apps.inventario.models import Stock, Ubicacion
        stock_vitrina = Stock.objects.filter(
            lote__producto=producto,
            ubicacion=Ubicacion.VITRINA,
            cantidad__gt=0,
        ).aggregate(total=Sum('cantidad'))['total'] or 0

        if nueva_cantidad > stock_vitrina:
            msg = f'Stock insuficiente en vitrina para {producto.nombre}. Disponible: {stock_vitrina} unidad(es).'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': msg}, status=400)
            messages.warning(request, msg)
            return redirect('ventas:punto_venta')

        item['cantidad'] = nueva_cantidad
        _guardar_carrito(request.session, carrito)

        if is_ajax:
            _, total = _resolver_carrito(carrito)
            subtotal = producto.precio_venta * nueva_cantidad
            return JsonResponse({
                'ok': True,
                'cantidad': nueva_cantidad,
                'subtotal': f'${subtotal}',
                'total': int(total),
                'total_formateado': f'${round(total)} CLP',
                'deshabilitar_menos': nueva_cantidad <= 1,
            })

        return redirect('ventas:punto_venta')


class FinalizarVentaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'ventas.add_venta'

    def post(self, request):
        caja = _caja_abierta_de(request.user)
        if not caja:
            messages.error(request, 'No tienes una caja abierta.')
            return redirect('ventas:abrir_caja')

        carrito = _get_carrito(request.session)
        if not carrito:
            messages.error(request, 'El carrito está vacío.')
            return redirect('ventas:punto_venta')

        form = FinalizarVentaForm(request.POST)
        if not form.is_valid():
            for errores in form.errors.values():
                for error in errores:
                    messages.error(request, error)
            return redirect('ventas:punto_venta')

        lineas = []
        for item in carrito:
            producto = Producto.objects.get(pk=item['producto_id'])
            receta_detalle = None
            if item.get('receta_detalle_id'):
                receta_detalle = RecetaDetalle.objects.get(pk=item['receta_detalle_id'])
            lineas.append({
                'producto': producto, 'cantidad': item['cantidad'], 'receta_detalle': receta_detalle,
                'retirado_por': item.get('retirado_por'),
            })

        try:
            venta = services.registrar_venta(
                caja=caja, vendedor=request.user, metodo_pago=form.cleaned_data['metodo_pago'],
                lineas=lineas, cliente=form.cleaned_data['cliente'],
            )
        except ValueError as error:
            messages.error(request, str(error))
            return redirect('ventas:punto_venta')

        tipo_doc = DocumentoTributario.Tipo.FACTURA if form.cleaned_data['emitir_factura'] else DocumentoTributario.Tipo.BOLETA
        try:
            services.emitir_documento(venta, tipo_doc)
        except ValueError as error:
            messages.warning(request, f'Venta registrada, pero no se pudo emitir el documento: {error}')

        _guardar_carrito(request.session, [])
        messages.success(request, f'Venta #{venta.pk} registrada correctamente.')
        return redirect('ventas:detalle_venta', pk=venta.pk)


class VentaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Listado del historial de ventas."""
    model = Venta
    template_name = 'ventas/venta_lista.html'
    permission_required = 'ventas.view_venta'
    context_object_name = 'ventas'
    paginate_by = 20

    def get_queryset(self):
        qs = Venta.objects.select_related('cliente', 'vendedor', 'documento_tributario').order_by('-fecha')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        
        busqueda = self.request.GET.get('q')
        if busqueda:
            qs = qs.filter(
                Q(pk__icontains=busqueda) | 
                Q(cliente__nombres__icontains=busqueda) |
                Q(cliente__apellidos__icontains=busqueda)
            )
        return qs
        
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'filtros': self.request.GET}


class CajaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Listado del historial de cajas."""
    model = Caja
    template_name = 'ventas/caja_lista.html'
    permission_required = 'ventas.view_caja'
    context_object_name = 'cajas'
    paginate_by = 20

    def get_queryset(self):
        qs = Caja.objects.select_related('usuario').order_by('-fecha_apertura')
        return qs


class DetalleVentaView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Venta
    template_name = 'ventas/detalle_venta.html'
    permission_required = 'ventas.view_venta'
    context_object_name = 'venta'


class ImprimirDocumentoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Imprime el documento tributario de una venta con la plantilla oficial
    de la farmacia. Se abre en el visor del navegador para poder imprimir."""

    permission_required = 'ventas.view_venta'

    def get(self, request, pk):
        venta = get_object_or_404(Venta.objects.select_related('cliente', 'vendedor'), pk=pk)
        documento = getattr(venta, 'documento_tributario', None)
        if documento is None:
            messages.error(request, 'Esta venta no tiene un documento tributario emitido.')
            return redirect('ventas:detalle_venta', pk=venta.pk)

        contexto = {'venta': venta, 'documento': documento, 'detalles': venta.detalles.select_related('producto', 'convenio')}
        nombre = f'{documento.get_tipo_display().lower()}_{documento.folio}'
        return render_pdf_response('ventas/pdf_documento.html', contexto, nombre, inline=True)


class AnularVentaView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = 'ventas/anular_venta.html'
    form_class = AnularVentaForm
    permission_required = 'ventas.change_venta'

    def dispatch(self, request, *args, **kwargs):
        self.venta = get_object_or_404(Venta, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'venta': self.venta}

    def form_valid(self, form):
        try:
            services.anular_venta(self.venta, self.request.user, form.cleaned_data['motivo'])
        except ValueError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        messages.success(self.request, f'Venta #{self.venta.pk} anulada.')
        return redirect('ventas:detalle_venta', pk=self.venta.pk)


class BuscarProductoAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Buscador inteligente de productos para el POS (vía fetch/AJAX)."""
    permission_required = 'ventas.add_venta'

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not query or len(query) < 2:
            return JsonResponse({'resultados': []})

        productos = (
            Producto.objects.filter(activo=True)
            .filter(
                Q(nombre__icontains=query) |
                Q(principio_activo__icontains=query) |
                Q(codigo_barras__icontains=query)
            )
            .annotate(stock_vitrina=Coalesce(Sum('lotes__stocks__cantidad', filter=Q(lotes__stocks__ubicacion='VITRINA')), 0))
            .order_by('-stock_vitrina', 'nombre')[:15]
        )

        resultados = []
        for p in productos:
            resultados.append({
                'id': p.pk,
                'codigo_barras': p.codigo_barras,
                'nombre': p.nombre,
                'principio_activo': p.principio_activo,
                'precio_venta': p.precio_venta,
                'requiere_receta': p.requiere_receta,
                'stock_vitrina': p.stock_vitrina,
            })
        return JsonResponse({'resultados': resultados})


class CrearClienteAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Creación rápida de clientes desde el POS."""
    permission_required = 'clientes.add_cliente'

    def post(self, request):
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse({
                'exito': True,
                'cliente': {
                    'id': cliente.pk,
                    'nombre_completo': cliente.nombre_completo,
                    'rut': cliente.rut
                }
            })
        
        # Recolectar errores para mostrarlos en el frontend
        errores = {field: error[0] for field, error in form.errors.items()}
        return JsonResponse({'exito': False, 'errores': errores}, status=400)


class DocumentoTributarioListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Listado de documentos tributarios (boletas, facturas) emitidos."""
    model = DocumentoTributario
    template_name = 'ventas/documento_lista.html'
    permission_required = 'ventas.view_venta'
    context_object_name = 'documentos'
    paginate_by = 30

    def get_queryset(self):
        qs = DocumentoTributario.objects.select_related('venta').order_by('-fecha_emision')
        
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(folio__icontains=busqueda) | 
                Q(venta__id__icontains=busqueda)
            )

        tipo = self.request.GET.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)
            
        return qs

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'filtros': self.request.GET,
            'tipos_documento': DocumentoTributario.Tipo.choices,
        }
