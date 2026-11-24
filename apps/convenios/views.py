from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import ConvenioForm
from .models import ClienteConvenio, Convenio


class ConvenioListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Lista de convenios activos e inactivos con filtro por tipo (RFP-08)."""

    template_name = 'convenios/convenio_lista.html'
    permission_required = 'convenios.view_convenio'
    context_object_name = 'convenios'

    def get_queryset(self):
        qs = Convenio.objects.annotate(
            total_afiliados=Count('afiliados', distinct=True),
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nombre__icontains=q)

        tipo = self.request.GET.get('tipo')
        if tipo in ('ISAPRE', 'SEGURO_COMPLEMENTARIO'):
            qs = qs.filter(tipo=tipo)

        estado = self.request.GET.get('estado')
        if estado == 'activos':
            qs = qs.filter(activo=True)
        elif estado == 'inactivos':
            qs = qs.filter(activo=False)

        return qs.order_by('nombre')

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'tipos': Convenio.Tipo.choices,
            'filtros': self.request.GET,
        }


class ConvenioDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Detalle del convenio con sus coberturas por categoría y afiliados activos (RFP-08)."""

    model = Convenio
    template_name = 'convenios/convenio_detalle.html'
    permission_required = 'convenios.view_convenio'
    context_object_name = 'convenio'

    def get_context_data(self, **kwargs):
        hoy = timezone.localdate()
        convenio = self.object
        coberturas = convenio.coberturas.select_related('categoria').order_by('categoria__nombre')
        afiliados = (
            ClienteConvenio.objects
            .filter(convenio=convenio, vigente_desde__lte=hoy)
            .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=hoy))
            .select_related('cliente')
            .order_by('cliente__apellidos')
        )
        return {
            **super().get_context_data(**kwargs),
            'coberturas': coberturas,
            'afiliados': afiliados,
        }


class ConvenioCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Crear un nuevo convenio con su nombre, tipo y descuento base (RFP-08)."""

    model = Convenio
    form_class = ConvenioForm
    template_name = 'convenios/convenio_form.html'
    permission_required = 'convenios.add_convenio'

    def get_success_url(self):
        return reverse_lazy('convenios:detalle', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'Convenio "{form.instance.nombre}" creado.')
        return super().form_valid(form)


class ConvenioUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Editar un convenio existente."""

    model = Convenio
    form_class = ConvenioForm
    template_name = 'convenios/convenio_form.html'
    permission_required = 'convenios.change_convenio'

    def get_success_url(self):
        return reverse_lazy('convenios:detalle', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'Convenio "{form.instance.nombre}" actualizado.')
        return super().form_valid(form)


class ClienteConvenioListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Listado de afiliaciones de clientes a convenios (Isapres/Seguros)."""
    model = ClienteConvenio
    template_name = 'convenios/afiliaciones_lista.html'
    permission_required = 'convenios.view_clienteconvenio'
    context_object_name = 'afiliaciones'
    paginate_by = 20

    def get_queryset(self):
        qs = ClienteConvenio.objects.select_related('cliente', 'convenio').order_by('-vigente_desde')
        busqueda = self.request.GET.get('q')
        if busqueda:
            qs = qs.filter(
                Q(cliente__nombres__icontains=busqueda) |
                Q(cliente__apellidos__icontains=busqueda) |
                Q(cliente__rut__icontains=busqueda) |
                Q(convenio__nombre__icontains=busqueda)
            )
        return qs
        
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'filtros': self.request.GET}
