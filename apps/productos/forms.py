from django import forms

from apps.comun.forms import BootstrapFormMixin

from .models import Categoria, Producto


class ProductoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre', 'principio_activo', 'laboratorio', 'presentacion', 'categoria',
            'tipo', 'nivel_control', 'categoria_regulatoria', 'codigo_barras',
            'precio_venta', 'stock_minimo', 'activo',
        ]

    def clean(self):
        datos = super().clean()
        nivel = datos.get('nivel_control')
        regulatoria = datos.get('categoria_regulatoria')
        # Estupefacientes y psicotrópicos solo tienen sentido en productos de
        # receta retenida; marcarlos en otro nivel deja el libro de control
        # (ISP) inconsistente con lo que realmente exige receta.
        if regulatoria and regulatoria != Producto.CategoriaRegulatoria.NINGUNA:
            if nivel != Producto.NivelControl.RECETA_RETENIDA:
                self.add_error(
                    'categoria_regulatoria',
                    'Solo los productos de receta retenida pueden clasificarse como estupefaciente o psicotrópico.',
                )
        return datos


class CategoriaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion']
