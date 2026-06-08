"""
URL configuration for sistema_evaluacion project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from rh import views  # <-- ESTA ES LA LÍNEA MÁGICA QUE FALTABA
from rh.admin import admin_site

urlpatterns = [
    # 1. TRASLADAMOS LA RUTA AL INICIO (Antes de admin.site.urls)
    path('admin/descargar-plantilla/<str:model_name>/', views.descargar_plantilla_excel, name='descargar_plantilla'),
    path('admin/resumen-evaluaciones/excel/', views.exportar_resumen_excel, name='exportar_resumen_excel'), # ⬅️ Agregada aquí arriba
    path('admin/resumen-evaluaciones/', views.resumen_evaluaciones_view, name='resumen_evaluaciones'),    
    path('admin/panel-evaluacion/', views.panel_evaluacion_view, name='panel_evaluacion'),    
    
    # 2. El administrador de Django se queda abajo
    #path('admin/', admin.site.urls),
    path('admin/', admin_site.urls),  # ⬅️ Cambiamos admin.site.urls por admin_site.urls
    
    # 3. Tus rutas de procesamiento de formularios
    path('evaluacion/guardar/', views.guardar_evaluacion_view, name='guardar_evaluacion'),
    path('panel-evaluacion/<int:subordinado_id>/', views.panel_evaluacion_view, name='panel_evaluacion'),
]


