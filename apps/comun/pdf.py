import io

from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def render_pdf_response(template_name, contexto, nombre_archivo, inline=False):
    """Renderiza un template a PDF y lo devuelve como respuesta HTTP.
    inline=True lo abre en el visor del navegador (para imprimir), en vez de
    forzar la descarga."""
    html = render_to_string(template_name, contexto)
    buffer = io.BytesIO()
    pisa.CreatePDF(html, dest=buffer)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    disposicion = 'inline' if inline else 'attachment'
    response['Content-Disposition'] = f'{disposicion}; filename="{nombre_archivo}.pdf"'
    return response
