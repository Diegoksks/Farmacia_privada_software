from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import ClienteForm
from .models import Cliente


class ClienteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'clientes/cliente_lista.html'
    permission_required = 'clientes.view_cliente'
    context_object_name = 'clientes'
    paginate_by = 20

    def get_queryset(self):
        queryset = Cliente.objects.prefetch_related('convenios__convenio')

        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            # El RUT se guarda sin puntos, así que se limpia lo escrito para
            # que "12.345.678-5" encuentre igual que "12345678".
            rut_buscado = busqueda.replace('.', '')
            queryset = queryset.filter(
                Q(rut__icontains=rut_buscado)
                | Q(nombres__icontains=busqueda)
                | Q(apellidos__icontains=busqueda)
                | Q(email__icontains=busqueda)
                | Q(telefono__icontains=busqueda)
            )

        estado = self.request.GET.get('estado')
        if estado == 'activos':
            queryset = queryset.filter(activo=True)
        elif estado == 'inactivos':
            queryset = queryset.filter(activo=False)

        return queryset

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'filtros': self.request.GET}


class ClienteDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Cliente
    template_name = 'clientes/cliente_detalle.html'
    permission_required = 'clientes.view_cliente'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        cliente = self.object
        hoy = timezone.localdate()

        convenios = [
            afiliacion for afiliacion in cliente.convenios.select_related('convenio')
            if afiliacion.vigente(hoy)
        ]
        recetas = cliente.recetas.prefetch_related('detalles__producto').order_by('-fecha_emision')[:5]
        ventas = cliente.ventas.order_by('-fecha')[:5]
        con_saldo = sum(
            1 for receta in cliente.recetas.filter(fecha_emision__lte=hoy, fecha_vencimiento__gte=hoy)
            for detalle in receta.detalles.all() if detalle.con_saldo
        )

        return {
            **super().get_context_data(**kwargs),
            'convenios_vigentes': convenios,
            'recetas': recetas,
            'ventas': ventas,
            'recetas_con_saldo': con_saldo,
        }


class ClienteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    permission_required = 'clientes.add_cliente'

    def get_success_url(self):
        return reverse_lazy('clientes:detalle', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'Cliente "{form.instance.nombre_completo}" registrado.')
        return super().form_valid(form)


class ClienteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    permission_required = 'clientes.change_cliente'

    def get_success_url(self):
        return reverse_lazy('clientes:detalle', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Datos del cliente actualizados.')
        return super().form_valid(form)


class ClienteToggleActivoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Activa o desactiva un cliente. No se borra: sus recetas y ventas deben
    seguir siendo consultables para la trazabilidad."""

    permission_required = 'clientes.change_cliente'

    def post(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        cliente.activo = not cliente.activo
        cliente.save(update_fields=['activo'])
        estado = 'activado' if cliente.activo else 'desactivado'
        messages.success(request, f'Cliente "{cliente.nombre_completo}" {estado}.')
        return redirect('clientes:lista')
