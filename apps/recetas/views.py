from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.clientes.models import Cliente

from .forms import RecetaDetalleFormSet, RecetaForm
from .models import DispensacionReceta, LibroControl, Receta


class RecetaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Lista paginada de recetas con filtros por estado (vigente/vencida),
    cliente y médico. Permite al personal encontrar rápidamente recetas con
    saldo disponible para dispensar (RFP-09)."""

    template_name = 'recetas/receta_lista.html'
    permission_required = 'recetas.view_receta'
    context_object_name = 'recetas'
    paginate_by = 20

    def get_queryset(self):
        hoy = timezone.localdate()
        qs = (
            Receta.objects
            .select_related('cliente', 'creado_por')
            .prefetch_related('detalles__producto')
            .order_by('-fecha_emision')
        )

        # Búsqueda por texto libre
        q = self.request.GET.get('q', '').strip()
        if q:
            rut_buscado = q.replace('.', '')
            qs = qs.filter(
                Q(cliente__rut__icontains=rut_buscado)
                | Q(cliente__nombres__icontains=q)
                | Q(cliente__apellidos__icontains=q)
                | Q(medico_nombre__icontains=q)
                | Q(medico_rut__icontains=rut_buscado)
                | Q(folio__icontains=q)
                | Q(detalles__producto__nombre__icontains=q)
            ).distinct()

        # Filtro por vigencia
        vigencia = self.request.GET.get('vigencia')
        if vigencia == 'vigentes':
            qs = qs.filter(fecha_emision__lte=hoy, fecha_vencimiento__gte=hoy)
        elif vigencia == 'vencidas':
            qs = qs.filter(fecha_vencimiento__lt=hoy)

        # Filtro por tipo de receta
        tipo = self.request.GET.get('tipo')
        if tipo in ('FISICA', 'DIGITAL'):
            qs = qs.filter(tipo=tipo)

        # Filtro por saldo pendiente
        con_saldo = self.request.GET.get('con_saldo')
        if con_saldo == '1':
            qs = qs.filter(
                detalles__cantidad_dispensada__lt=F('detalles__cantidad_prescrita'),
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'filtros': self.request.GET,
            'tipos': Receta.Tipo.choices,
        }


class RecetaDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Detalle completo de una receta: datos del médico, paciente, medicamentos
    prescritos con saldo restante y el historial de dispensaciones (RFP-09/10)."""

    model = Receta
    template_name = 'recetas/receta_detalle.html'
    permission_required = 'recetas.view_receta'
    context_object_name = 'receta'

    def get_queryset(self):
        return (
            Receta.objects
            .select_related('cliente', 'creado_por')
            .prefetch_related(
                'detalles__producto',
                'detalles__dispensaciones__usuario',
            )
        )


class RecetaCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Registra una nueva receta médica junto con sus medicamentos prescritos
    (formset). El campo creado_por se asigna automáticamente al usuario actual
    (RFP-09)."""

    model = Receta
    form_class = RecetaForm
    template_name = 'recetas/receta_form.html'
    permission_required = 'recetas.add_receta'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = RecetaDetalleFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = RecetaDetalleFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if not formset.is_valid():
            return self.form_invalid(form)

        form.instance.creado_por = self.request.user
        self.object = form.save()
        formset.instance = self.object
        formset.save()
        messages.success(
            self.request,
            f'Receta #{self.object.pk} registrada para {self.object.cliente.nombre_completo}.',
        )
        return redirect('recetas:detalle', pk=self.object.pk)

    def form_invalid(self, form):
        messages.error(self.request, 'Corrige los errores antes de guardar.')
        return super().form_invalid(form)


class RecetaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Permite editar el encabezado de una receta (datos del médico, fechas).
    Los detalles de medicamentos se editan desde el formset inline."""

    model = Receta
    form_class = RecetaForm
    template_name = 'recetas/receta_form.html'
    permission_required = 'recetas.change_receta'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = RecetaDetalleFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = RecetaDetalleFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if not formset.is_valid():
            return self.form_invalid(form)

        self.object = form.save()
        formset.instance = self.object
        formset.save()
        messages.success(self.request, f'Receta #{self.object.pk} actualizada.')
        return redirect('recetas:detalle', pk=self.object.pk)

    def get_success_url(self):
        return reverse_lazy('recetas:detalle', kwargs={'pk': self.object.pk})


class DispensacionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DispensacionReceta
    template_name = 'recetas/dispensacion_lista.html'
    context_object_name = 'dispensaciones'
    permission_required = 'recetas.view_dispensacionreceta'
    paginate_by = 30

    def get_queryset(self):
        return DispensacionReceta.objects.select_related(
            'detalle__receta__cliente',
            'detalle__producto',
            'usuario'
        ).order_by('-fecha')


class LibroControlListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LibroControl
    template_name = 'recetas/libro_control.html'
    context_object_name = 'entradas'
    permission_required = 'recetas.view_librocontrol'
    paginate_by = 30

    def get_queryset(self):
        qs = LibroControl.objects.select_related(
            'detalle__receta__cliente',
            'detalle__producto'
        ).order_by('-fecha')
        
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(detalle__producto__nombre__icontains=busqueda) | 
                Q(detalle__receta__cliente__rut__icontains=busqueda)
            )
        return qs
        
    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'filtros': self.request.GET,
        }

from django.views import View
from django.http import JsonResponse
from .services import obtener_pacientes_cronicos, enviar_recordatorio_correo

class RecordatoriosListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'recetas/recordatorios.html'
    permission_required = 'recetas.view_receta'
    context_object_name = 'detalles'
    
    def get_queryset(self):
        return obtener_pacientes_cronicos()

class EnviarRecordatoriosApiView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'recetas.change_receta'
    
    def post(self, request, *args, **kwargs):
        detalles = obtener_pacientes_cronicos()
        enviados = 0
        fallidos = 0
        
        for detalle in detalles:
            try:
                exito = enviar_recordatorio_correo(detalle)
                if exito:
                    enviados += 1
                else:
                    fallidos += 1
            except Exception as e:
                print(f"Error enviando correo a {detalle.receta.cliente.email}: {e}")
                fallidos += 1
                
        return JsonResponse({
            'enviados': enviados,
            'fallidos': fallidos,
            'total': len(detalles)
        })
