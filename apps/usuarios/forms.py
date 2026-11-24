from django import forms
from django.contrib.auth.forms import AuthenticationForm
from apps.comun.forms import NormalizarRutFormMixin

from .models import Usuario


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'form-control'


class CodigoVerificacionForm(forms.Form):
    codigo = forms.CharField(
        max_length=6,
        min_length=6,
        label='Código de verificación',
        widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True, 'inputmode': 'numeric'}),
    )


class UsuarioAdminForm(NormalizarRutFormMixin, forms.ModelForm):
    """Mismo problema del RUT que en clientes: sin normalizar antes de validar,
    escribirlo con puntos evade la verificación de unicidad y falla al guardar."""

    class Meta:
        model = Usuario
        fields = '__all__'


class UsuarioCreateForm(NormalizarRutFormMixin, forms.ModelForm):
    """Formulario para crear un usuario desde el frontend.
    Se exige RUT, Nombres, Apellidos, Email y Rol."""
    
    # Añadimos first_name y last_name explícitamente y requeridos
    first_name = forms.CharField(label='Nombres', max_length=150, required=True)
    last_name = forms.CharField(label='Apellidos', max_length=150, required=True)

    class Meta:
        model = Usuario
        fields = ['rut', 'first_name', 'last_name', 'email', 'telefono', 'rol']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['rol'].widget.attrs['class'] = 'form-select'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Si el email fue provisto, chequear que no exista en otro usuario activo
        if email and Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo ya está en uso por otro usuario.")
        return email


class UsuarioUpdateForm(NormalizarRutFormMixin, forms.ModelForm):
    """Formulario para editar un usuario existente desde el frontend."""
    
    first_name = forms.CharField(label='Nombres', max_length=150, required=True)
    last_name = forms.CharField(label='Apellidos', max_length=150, required=True)
    is_active = forms.BooleanField(label='Usuario activo', required=False, 
                                   help_text='Desmárcalo para impedir que el usuario inicie sesión.')

    class Meta:
        model = Usuario
        fields = ['rut', 'first_name', 'last_name', 'email', 'telefono', 'rol', 'is_active']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'is_active':
                field.widget.attrs['class'] = 'form-control'
        self.fields['rol'].widget.attrs['class'] = 'form-select'
        self.fields['is_active'].widget.attrs['class'] = 'form-check-input'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Usuario.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este correo ya está en uso por otro usuario.")
        return email
