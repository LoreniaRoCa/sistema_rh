from django.shortcuts import redirect

class RestringirAccesoAdminMiddleware:
    """
    Middleware que bloquea el acceso al inicio/menú de admin /admin/ 
    a cualquier usuario que NO sea superusuario, mandándolo a su panel.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Normalizamos la ruta quitando la barra final para capturar '/admin' y '/admin/'
            path_limpia = request.path.rstrip('/')

            # Si el usuario NO es superadministrador e intenta entrar a la raíz o al admin
            if not request.user.is_superuser:
                if path_limpia in ['/admin', '']:
                    return redirect('panel_evaluacion')

        response = self.get_response(request)
        return response