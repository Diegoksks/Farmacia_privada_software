import unicodedata
from django import template

register = template.Library()

DICCIONARIO_MODELOS = {
    'group': 'roles y grupos',
    'grupo': 'roles y grupos',
    'permission': 'permisos del sistema',
    'permiso': 'permisos del sistema',
    'user': 'usuarios',
    'usuario': 'usuarios',
    'cliente': 'clientes',
    'cliente convenio': 'convenios de clientes',
    'clienteconvenio': 'convenios de clientes',
    'afiliacion a convenio': 'convenios de clientes',
    'convenio': 'convenios',
    'convenio cobertura': 'coberturas de convenio',
    'conveniocobertura': 'coberturas de convenio',
    'cobertura por categoria': 'coberturas de convenio',
    'puntos fidelizacion': 'puntos de fidelización',
    'puntosfidelizacion': 'puntos de fidelización',
    'movimiento de puntos': 'puntos de fidelización',
    'categoria': 'categorías de productos',
    'producto': 'productos',
    'lote': 'lotes de medicamentos',
    'stock': 'stock en inventario',
    'movimiento stock': 'movimientos de stock',
    'movimientostock': 'movimientos de stock',
    'movimiento de stock': 'movimientos de stock',
    'ubicacion': 'ubicaciones de inventario',
    'orden compra': 'órdenes de compra',
    'ordencompra': 'órdenes de compra',
    'orden compra detalle': 'detalles de órdenes de compra',
    'ordencompradetalle': 'detalles de órdenes de compra',
    'linea de orden de compra': 'detalles de órdenes de compra',
    'proveedor': 'proveedores',
    'receta': 'recetas médicas',
    'receta detalle': 'detalles de recetas',
    'recetadetalle': 'detalles de recetas',
    'linea de receta': 'detalles de recetas',
    'dispensacion receta': 'dispensaciones de recetas',
    'dispensacionreceta': 'dispensaciones de recetas',
    'dispensacion de receta': 'dispensaciones de recetas',
    'libro control': 'libro de control (ISP)',
    'librocontrol': 'libro de control (ISP)',
    'entrada del libro de control': 'libro de control (ISP)',
    'venta': 'ventas',
    'venta detalle': 'detalles de ventas',
    'ventadetalle': 'detalles de ventas',
    'linea de venta': 'detalles de ventas',
    'venta detalle lote': 'lotes consumidos en ventas',
    'ventadetallelote': 'lotes consumidos en ventas',
    'lote consumido en venta': 'lotes consumidos en ventas',
    'caja': 'cajas y turnos',
    'documento tributario': 'documentos tributarios',
    'documentotributario': 'documentos tributarios',
    'codigo verificacion': 'códigos de verificación 2FA',
    'codigoverificacion': 'códigos de verificación 2FA',
    'codigo de verificacion': 'códigos de verificación 2FA',
    'chat mensaje': 'mensajes del asistente IA',
    'chatmensaje': 'mensajes del asistente IA',
    'mensaje de chat': 'mensajes del asistente IA',
    'log entry': 'registros de auditoría',
    'logentry': 'registros de auditoría',
    'entrada de registro': 'registros de auditoría',
    'content type': 'tipos de contenido',
    'contenttype': 'tipos de contenido',
    'session': 'sesiones de usuario',
}

def normalizar_texto(texto):
    """Elimina acentos y caracteres especiales para búsqueda tolerante."""
    if not texto:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    ).strip()

@register.filter(name='traducir_permiso')
def traducir_permiso(nombre):
    """
    Traduce nombres de permisos estándar de Django como:
    'Can add cliente' -> 'Puede agregar clientes'
    'Can view orden compra detalle' -> 'Puede ver detalles de órdenes de compra'
    """
    if not nombre:
        return ''

    texto = str(nombre).strip()
    prefijos = [
        ('Can add ', 'Puede agregar '),
        ('Can change ', 'Puede modificar '),
        ('Can delete ', 'Puede eliminar '),
        ('Can view ', 'Puede ver '),
    ]

    for eng, esp in prefijos:
        if texto.startswith(eng):
            resto_original = texto[len(eng):].strip()
            resto_norm = normalizar_texto(resto_original)
            
            # Buscar coincidencia directa
            modelo_traducido = DICCIONARIO_MODELOS.get(resto_norm)
            if not modelo_traducido:
                # Buscar sin espacios o con guiones
                modelo_traducido = DICCIONARIO_MODELOS.get(resto_norm.replace(' ', ''))
            
            if modelo_traducido:
                return f"{esp}{modelo_traducido}"
            return f"{esp}{resto_original}"

    return texto
