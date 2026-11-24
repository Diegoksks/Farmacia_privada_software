from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import F
from .models import RecetaDetalle, DispensacionReceta


@transaction.atomic
def dispensar(detalle: RecetaDetalle, cantidad: int, usuario, observacion: str = '', retirado_por: dict = None):
    """
    Registra la entrega/dispensación de medicamentos contra una receta médica,
    validando vigencia y saldo, y guardando trazabilidad de quién retiró.
    """
    if cantidad <= 0:
        raise ValueError('La cantidad a dispensar debe ser mayor a 0.')

    detalle = RecetaDetalle.objects.select_for_update().get(pk=detalle.pk)
    receta = detalle.receta
    if not receta.esta_vigente:
        raise ValueError(f'La receta #{receta.pk} está vencida (venció el {receta.fecha_vencimiento}).')

    if cantidad > detalle.saldo:
        raise ValueError(
            f'Saldo insuficiente en la receta: solicita {cantidad} pero solo quedan {detalle.saldo} unidades disponibles.'
        )

    retirado_por = retirado_por or {}
    disp = DispensacionReceta.objects.create(
        detalle=detalle,
        cantidad=cantidad,
        usuario=usuario,
        observacion=observacion,
        retirado_por_nombre=retirado_por.get('nombre', ''),
        retirado_por_rut=retirado_por.get('rut', ''),
        retirado_por_relacion=retirado_por.get('relacion', ''),
    )

    detalle.cantidad_dispensada += cantidad
    detalle.save(update_fields=['cantidad_dispensada'])
    return disp


def obtener_pacientes_cronicos():
    """
    Obtiene las líneas de receta que no han sido despachadas por completo 
    y cuya fecha de vencimiento aún es válida.
    """
    hoy = timezone.localdate()
    # Tratamientos crónicos activos
    detalles = RecetaDetalle.objects.select_related(
        'receta', 'receta__cliente', 'producto'
    ).filter(
        cantidad_dispensada__lt=F('cantidad_prescrita'),
        receta__fecha_vencimiento__gte=hoy
    ).order_by('receta__fecha_vencimiento')
    return detalles

def enviar_recordatorio_correo(detalle: RecetaDetalle):
    """
    Envía un correo electrónico al cliente recordando que tiene saldo pendiente.
    """
    cliente = detalle.receta.cliente
    if not cliente.email:
        return False
        
    producto = detalle.producto.nombre
    restante = detalle.cantidad_prescrita - detalle.cantidad_dispensada
    
    asunto = f"Aviso de Farmacia Privada: Recordatorio de Tratamiento Crónico"
    mensaje = (
        f"Estimado/a {cliente.nombre_completo},\n\n"
        f"Le escribimos de Farmacia Privada para recordarle que aún tiene "
        f"saldo disponible de {restante} unidades de su tratamiento crónico ({producto}).\n\n"
        f"Su receta médica vence el {detalle.receta.fecha_vencimiento.strftime('%d/%m/%Y')}. "
        f"Por favor, acérquese a nuestra sucursal para realizar el retiro o compra antes de que caduque su prescripción.\n\n"
        f"Atentamente,\n"
        f"Equipo de Farmacia Privada."
    )
    
    send_mail(
        subject=asunto,
        message=mensaje,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@farmaciaprivada.com'),
        recipient_list=[cliente.email],
        fail_silently=False,
    )
    return True
