from django import forms
from django.db.models import F
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.comun.forms import BootstrapFormMixin
from apps.comun.validators import validar_rut
from apps.recetas.models import RecetaDetalle

from .models import Venta


class AbrirCajaForm(BootstrapFormMixin, forms.Form):
    monto_apertura = forms.IntegerField(min_value=0, label='Monto inicial en caja (CLP)')


class CerrarCajaForm(BootstrapFormMixin, forms.Form):
    monto_declarado = forms.IntegerField(min_value=0, label='Monto contado físicamente (CLP)')


class AgregarPorCodigoBarrasForm(BootstrapFormMixin, forms.Form):
    codigo_barras = forms.CharField(label='Código de barras')
    cantidad = forms.IntegerField(min_value=1, initial=1)


class RecetaDetalleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.receta.cliente.nombre_completo} — {obj.producto.nombre} (saldo: {obj.saldo})'


class AgregarPorRecetaForm(BootstrapFormMixin, forms.Form):
    receta_detalle = RecetaDetalleChoiceField(
        queryset=RecetaDetalle.objects.none(),
        label='Receta con saldo',
        empty_label='- Seleccione una opción -',
    )
    cantidad = forms.IntegerField(min_value=1, initial=1)
    retirado_por_nombre = forms.CharField(
        required=False, label='Retira un tercero (nombre)',
        help_text='Deja en blanco si retira el propio paciente.',
    )
    retirado_por_rut = forms.CharField(required=False, label='RUT de quien retira', validators=[validar_rut])
    retirado_por_relacion = forms.CharField(required=False, label='Relación con el paciente')

    def clean(self):
        datos = super().clean()
        if (datos.get('retirado_por_rut') or datos.get('retirado_por_relacion')) and not datos.get('retirado_por_nombre'):
            self.add_error('retirado_por_nombre', 'Indica el nombre de quien retira.')
        return datos

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = timezone.localdate()
        self.fields['receta_detalle'].queryset = (
            RecetaDetalle.objects
            .filter(
                cantidad_dispensada__lt=F('cantidad_prescrita'),
                receta__fecha_emision__lte=hoy,
                receta__fecha_vencimiento__gte=hoy,
            )
            .select_related('receta__cliente', 'producto')
        )


class FinalizarVentaForm(BootstrapFormMixin, forms.Form):
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(activo=True),
        required=False,
        label='Cliente',
        empty_label='- Seleccione una opción -',
    )
    metodo_pago = forms.ChoiceField(choices=Venta.MetodoPago.choices)
    emitir_factura = forms.BooleanField(required=False, label='Emitir factura (requiere cliente)')

    def clean(self):
        datos = super().clean()
        if datos.get('emitir_factura') and not datos.get('cliente'):
            self.add_error('cliente', 'Selecciona un cliente para emitir la factura.')
        return datos


class AnularVentaForm(BootstrapFormMixin, forms.Form):
    motivo = forms.CharField(widget=forms.Textarea, label='Motivo de anulación')
