from django import forms
from django.forms.models import inlineformset_factory

from apps.comun.forms import BootstrapFormMixin

from .models import Lote, Ubicacion, OrdenCompra, OrdenCompraDetalle, Proveedor


class ProveedorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'rut', 'giro', 'contacto_nombre', 'telefono', 'email', 'direccion', 'ciudad', 'activo', 'notas']
        widgets = {
            'notas': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Condiciones comerciales, horarios de recepción, etc.'}),
        }


class TraspasoStockForm(BootstrapFormMixin, forms.Form):
    lote = forms.ModelChoiceField(
        queryset=Lote.objects.filter(stocks__ubicacion=Ubicacion.BODEGA, stocks__cantidad__gt=0).distinct(),
        label='Lote (con stock en bodega)',
        empty_label='- Seleccione una opción -',
    )
    cantidad = forms.IntegerField(min_value=1)
    observacion = forms.CharField(required=False, widget=forms.TextInput)


class AjusteStockForm(BootstrapFormMixin, forms.Form):
    lote = forms.ModelChoiceField(
        queryset=Lote.objects.all(),
        empty_label='- Seleccione una opción -',
    )
    ubicacion = forms.ChoiceField(choices=Ubicacion.choices)
    cantidad_delta = forms.IntegerField(
        label='Cantidad a ajustar',
        help_text='Positivo si aparece stock (conteo físico), negativo si se pierde (merma, daño, vencido).',
    )
    motivo = forms.CharField(widget=forms.TextInput)


class OrdenCompraForm(BootstrapFormMixin, forms.ModelForm):
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.filter(activo=True),
        empty_label='— Seleccionar un proveedor —',
        label='Proveedor',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_proveedor'}),
    )

    class Meta:
        model = OrdenCompra
        fields = ['proveedor', 'numero_factura', 'observaciones']
        widgets = {
            'numero_factura': forms.TextInput(attrs={'placeholder': 'Ej: FAC-10492 ó GDD-8812'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Condiciones de compra, plazo o notas...'}),
        }


class OrdenCompraDetalleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OrdenCompraDetalle
        fields = ['producto', 'fecha_vencimiento', 'cantidad', 'precio_unitario']
        widgets = {
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
        }


OrdenCompraDetalleFormSet = inlineformset_factory(
    OrdenCompra,
    OrdenCompraDetalle,
    form=OrdenCompraDetalleForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True
)
