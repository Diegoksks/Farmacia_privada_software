from django import forms

from apps.comun.forms import BootstrapFormMixin
from .models import Convenio


class ConvenioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Convenio
        fields = ['nombre', 'tipo', 'descuento_porcentaje', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: Isapre Banmédica',
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descuento_porcentaje': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100,
            }),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
