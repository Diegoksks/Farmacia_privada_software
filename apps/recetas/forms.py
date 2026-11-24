from django import forms
from django.forms import inlineformset_factory

from apps.clientes.models import Cliente
from apps.productos.models import Producto

from .models import Receta, RecetaDetalle


class RecetaForm(forms.ModelForm):
    """Formulario para crear o editar el encabezado de una receta médica."""

    class Meta:
        model = Receta
        fields = [
            'cliente', 'medico_rut', 'medico_nombre',
            'tipo', 'folio', 'fecha_emision', 'fecha_vencimiento',
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'medico_rut': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: 12345678-9',
            }),
            'medico_nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nombre completo del médico',
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'folio': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Opcional — folio del talonario',
            }),
            'fecha_emision': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d',
            ),
            'fecha_vencimiento': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = Cliente.objects.filter(activo=True)
        self.fields['cliente'].empty_label = 'Selecciona un cliente...'
        self.fields['folio'].required = False


class RecetaDetalleForm(forms.ModelForm):
    """Una línea de medicamento prescrito dentro de una receta."""

    class Meta:
        model = RecetaDetalle
        fields = ['producto', 'posologia', 'cantidad_prescrita']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'posologia': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Ej: 1 comp. cada 8 horas',
            }),
            'cantidad_prescrita': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 'min': 1,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar productos que requieren receta para evitar errores de validación
        self.fields['producto'].queryset = Producto.objects.filter(
            activo=True,
        ).exclude(nivel_control='VENTA_LIBRE').select_related('categoria')
        self.fields['producto'].empty_label = 'Selecciona medicamento...'


# Formset: permite múltiples líneas de medicamentos en un mismo form
RecetaDetalleFormSet = inlineformset_factory(
    Receta,
    RecetaDetalle,
    form=RecetaDetalleForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)
