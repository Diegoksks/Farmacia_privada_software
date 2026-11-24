from django import forms

from apps.comun.forms import BootstrapFormMixin, NormalizarRutFormMixin

from .models import Cliente


class ClienteForm(NormalizarRutFormMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['rut', 'nombres', 'apellidos', 'telefono', 'email', 'activo']
        widgets = {
            'rut': forms.TextInput(attrs={'placeholder': '12.345.678-5'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 1234 5678'}),
        }
