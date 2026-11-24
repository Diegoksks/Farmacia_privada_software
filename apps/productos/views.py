from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import CategoriaForm, ProductoForm
from .models import Categoria, Producto


class ProductoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'productos/producto_lista.html'
    permission_required = 'productos.view_producto'
    context_object_name = 'productos'
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            Producto.objects
            .annotate(stock_actual=Coalesce(Sum('lotes__stocks__cantidad'), 0))
            .select_related('categoria')
        )

        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda)
                | Q(principio_activo__icontains=busqueda)
                | Q(codigo_barras__icontains=busqueda)
                | Q(laboratorio__icontains=busqueda)
            )

        for campo in ('tipo', 'nivel_control', 'categoria'):
            valor = self.request.GET.get(campo)
            if valor:
                queryset = queryset.filter(**{campo: valor})

        estado = self.request.GET.get('estado')
        if estado == 'activos':
            queryset = queryset.filter(activo=True)
        elif estado == 'inactivos':
            queryset = queryset.filter(activo=False)

        return queryset.order_by('nombre')

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'categorias': Categoria.objects.all(),
            'tipos': Producto.Tipo.choices,
            'niveles': Producto.NivelControl.choices,
            'filtros': self.request.GET,
        }


class ProductoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'productos/producto_form.html'
    permission_required = 'productos.add_producto'
    success_url = reverse_lazy('productos:lista')

    def form_valid(self, form):
        messages.success(self.request, f'Producto "{form.instance.nombre}" creado.')
        return super().form_valid(form)


class ProductoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'productos/producto_form.html'
    permission_required = 'productos.change_producto'
    success_url = reverse_lazy('productos:lista')

    def form_valid(self, form):
        messages.success(self.request, f'Producto "{form.instance.nombre}" actualizado.')
        return super().form_valid(form)


class ProductoToggleActivoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Activa o desactiva un producto. No se borra nunca: el histórico de
    ventas, lotes y recetas lo referencia y debe seguir siendo consultable."""

    permission_required = 'productos.change_producto'

    def post(self, request, pk):
        producto = get_object_or_404(Producto, pk=pk)
        producto.activo = not producto.activo
        producto.save(update_fields=['activo'])
        estado = 'activado' if producto.activo else 'desactivado'
        messages.success(request, f'Producto "{producto.nombre}" {estado}.')
        return redirect('productos:lista')


class CategoriaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'productos/categoria_lista.html'
    permission_required = 'productos.view_categoria'
    context_object_name = 'categorias'

    def get_queryset(self):
        return Categoria.objects.annotate(
            unidades=Coalesce(Sum('productos__lotes__stocks__cantidad'), 0),
        )


class CategoriaCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'productos/categoria_form.html'
    permission_required = 'productos.add_categoria'
    success_url = reverse_lazy('productos:categoria_lista')

    def form_valid(self, form):
        messages.success(self.request, f'Categoría "{form.instance.nombre}" creada.')
        return super().form_valid(form)


class CategoriaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'productos/categoria_form.html'
    permission_required = 'productos.change_categoria'
    success_url = reverse_lazy('productos:categoria_lista')

    def form_valid(self, form):
        messages.success(self.request, f'Categoría "{form.instance.nombre}" actualizada.')
        return super().form_valid(form)
