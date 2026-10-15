from functools import wraps

from django.core.exceptions import PermissionDenied


def docente_required(view):
    @wraps(view)
    def interna(request, *args, **kwargs):
        if not request.user.is_docente:
            raise PermissionDenied("Você não tem permissão para acessar esta funcionalidade.")
        return view(request, *args, **kwargs)
    return interna