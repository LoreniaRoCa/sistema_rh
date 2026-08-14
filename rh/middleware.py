from django.shortcuts import redirect

class RestringirAccesoAdminMiddleware:
    """
    Middleware que bloquea el acceso a catálogos y secciones administrativas de /admin/* 
    a usuarios que NO sean superusuarios, permitiéndoles entrar ÚNICAMENTE a su panel de evaluación.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            path = request.path

            # Rutas del sistema que SÍ se le permiten a un empleado/evaluador
            rutas_permitidas = [
                '/admin/panel-evaluacion',
                '/admin/logout',
                '/cerrar-sesion',
                '/guardar-evaluacion',
                '/redireccionar-login',
            ]

            # Si intenta entrar a cualquier ruta de /admin/
            if path.startswith('/admin'):
                # Verificamos si la ruta actual es una de las permitidas
                es_permitida = any(path.startswith(prefix) for prefix in rutas_permitidas)

                # Si NO está permitida (ej. /admin/rh/empleado/), lo mandamos a su panel
                if not es_permitida:
                    return redirect('panel_evaluacion')

        response = self.get_response(request)
        return response