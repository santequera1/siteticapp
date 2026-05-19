from .models import Negocio


def negocio_context(request):
    try:
        negocio = Negocio.objects.first()
    except Exception:
        negocio = None
    return {'negocio': negocio}
