from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.core.mail import send_mail
from django.db import models  
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
import openpyxl
from unfold.admin import ModelAdmin, TabularInline  
from unfold.sites import UnfoldAdminSite  # ⬅️ ¡ESTA ES LA LÍNEA MÁGICA QUE FALTA!
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import connection
from .models import TokenAccesoEvaluacion, Empleado
class CustomAdminSite(UnfoldAdminSite):
    index_template = "admin/index.html"

class CustomAdminSite(UnfoldAdminSite):
    index_template = "admin/index.html"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        departamentos_dict = {}
        # Cambiamos jefes de lista a diccionario temporal para agrupar en Python
        jefes_dict = {} 
        
        total_global_empleados = 0
        total_ambas_completadas_global = 0
        total_auto_global = 0
        total_jefe_global = 0

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    departamento, 
                    jefe, 
                    numempleados, 
                    autoevaluados, 
                    evaluados,
                    ambas  -- ⬅️ Agregamos la nueva columna aquí (row[5])
                FROM vista_dashboard_departamentos
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                dep_nombre = row[0] or "Sin Departamento"
                jefe_nombre = row[1] or "Sin Jefe Asignado"
                
                num_emp = int(row[2] or 0)
                auto_ev = int(row[3] or 0)
                jefe_ev = int(row[4] or 0)
                ambas_ev = int(row[5] or 0)  

                # 1. MANTENER DEPARTAMENTOS INTACTOS
                if dep_nombre not in departamentos_dict:
                    departamentos_dict[dep_nombre] = {
                        'num_empleados': 0,
                        'auto_evaluados': 0,
                        'evaluados': 0,
                        'porcentaje': 0
                    }
                
                departamentos_dict[dep_nombre]['num_empleados'] += num_emp
                departamentos_dict[dep_nombre]['auto_evaluados'] += auto_ev
                departamentos_dict[dep_nombre]['evaluados'] += jefe_ev
                
                total_dep = departamentos_dict[dep_nombre]['num_empleados']
                autos_dep = departamentos_dict[dep_nombre]['auto_evaluados']
                if total_dep > 0:
                    departamentos_dict[dep_nombre]['porcentaje'] = round((autos_dep / total_dep) * 100)
                else:
                    departamentos_dict[dep_nombre]['porcentaje'] = 0

                # 2. ACTUALIZACIÓN DE KPIS GLOBALES CON LA COLUMNA CORRECTA
                total_global_empleados += num_emp
                total_auto_global += auto_ev
                total_jefe_global += jefe_ev
                total_ambas_completadas_global += ambas_ev  
                
                # 3. AGRUPACIÓN Y SUMARIZACIÓN POR JEFE
                if jefe_nombre not in jefes_dict:
                    jefes_dict[jefe_nombre] = {
                        'nombre': jefe_nombre,
                        'total_empleados': 0,
                        'auto_contestadas': 0,
                        'jefe_contestadas': 0,
                    }
                
                # Vamos acumulando los valores de todos los departamentos que pertenezcan a este jefe
                jefes_dict[jefe_nombre]['total_empleados'] += num_emp
                jefes_dict[jefe_nombre]['auto_contestadas'] += auto_ev
                jefes_dict[jefe_nombre]['jefe_contestadas'] += jefe_ev

        # --- POST-PROCESAMIENTO DE JEFES (Cálculo de porcentajes y colores) ---
        jefes_data = []
        for jefe_nombre, data in jefes_dict.items():
            tot_emp = data['total_empleados']
            auto_cont = data['auto_contestadas']
            jefe_cont = data['jefe_contestadas']

            # Calcular porcentajes sobre los totales agrupados del jefe
            auto_pct = round((auto_cont / tot_emp * 100), 1) if tot_emp > 0 else 0.0
            jefe_pct = round((jefe_cont / tot_emp * 100), 1) if tot_emp > 0 else 0.0

            # Lógica de colores de semáforos para las barras de progreso
            color_auto = "#ef4444" if auto_pct < 40 else ("#f59e0b" if auto_pct < 85 else "#72a651")
            color_jefe = "#ef4444" if jefe_pct < 40 else ("#f59e0b" if jefe_pct < 85 else "#72a651")

            jefes_data.append({
                'nombre': jefe_nombre,
                'total_empleados': tot_emp,
                'auto_contestadas': auto_cont,
                'auto_pct': auto_pct,
                'color_auto': color_auto,
                'jefe_contestadas': jefe_cont,
                'jefe_pct': jefe_pct,
                'color_jefe': color_jefe,
            })

        # Ordenar alfabéticamente por nombre de jefe
        jefes_data = sorted(jefes_data, key=lambda x: x['nombre'])

        # --- CÁLCULO DE KPIS GLOBAL ---
        pct_general = round((total_ambas_completadas_global / total_global_empleados * 100), 1) if total_global_empleados > 0 else 0
        pct_auto = round((total_auto_global / total_global_empleados * 100), 1) if total_global_empleados > 0 else 0
        pct_jefe = round((total_jefe_global / total_global_empleados * 100), 1) if total_global_empleados > 0 else 0

        offset_general = round(251.2 * (1 - (pct_general / 100)), 1)
        offset_auto = round(251.2 * (1 - (pct_auto / 100)), 1)
        offset_jefe = round(251.2 * (1 - (pct_jefe / 100)), 1)

        extra_context["global_kpis"] = {
            "general_completadas": total_ambas_completadas_global,
            "general_porcentaje": pct_general,
            "general_offset": offset_general,
            "auto_contestadas": total_auto_global,
            "auto_porcentaje": pct_auto,
            "auto_offset": offset_auto,
            "jefe_contestadas": total_jefe_global,
            "jefe_porcentaje": pct_jefe,
            "jefe_offset": offset_jefe,
        }

        extra_context["departamentos"] = departamentos_dict
        extra_context["jefes_data"] = jefes_data

        return super().index(request, extra_context=extra_context)

# Instanciación del sitio personalizado
admin_site = CustomAdminSite(name='custom_admin')

# Desasociamos los registros por defecto (en caso de ser necesario)
# e incorporamos el soporte de visualización para tu panel personalizado de Unfold
try:
    admin.site.unregister(User)
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

# Registramos Usuarios y Grupos para que tu URLconf sepa que existen en /admin/
# Registramos Usuarios y Grupos para que tu URLconf sepa que existen en tu 'admin_site' personalizado de Unfold
@admin.register(User, site=admin_site)  # 🌟 Agregamos 'site=admin_site' para que se vinculen a tu dashboard
class UserAdmin(BaseUserAdmin, ModelAdmin):
    pass

@admin.register(Group, site=admin_site) # 🌟 Agregamos 'site=admin_site' para que se vinculen a tu dashboard
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


# Importación explícita de todos los modelos requeridos
from .models import (
    Puesto, Departamento, Empleado, CompetenciaClasificacion, 
    Competencia, Evaluacion, EvaluacionDet, ClasificacionPorPuesto, 
    ClasificacionPorEmpleado, EmpleadoCompetenciaAsignada
)



class CatalogosOrdenadosAdmin(admin.ModelAdmin):
    """
    Clase base para que todos los combos (ForeignKeys) del sistema
    se ordenen alfabéticamente de forma automática, sin alterar el listado principal.
    """
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # 1. Obtenemos el modelo al que apunta esta clave heredada
        target_model = db_field.remote_field.model
        campos = [f.name for f in target_model._meta.fields]

        # 2. Si el modelo tiene un campo 'nombre_largo' o 'descripcion', ordenamos por él
        if 'nombre_largo' in campos:
            kwargs["queryset"] = target_model.objects.order_by('nombre_largo')
        elif 'descripcion' in campos:
            kwargs["queryset"] = target_model.objects.order_by('descripcion')
        elif 'nombre' in campos:
            kwargs["queryset"] = target_model.objects.order_by('nombre')

        return super().formfield_for_foreignkey(db_field, request, **kwargs)
class ExcelUploadForm(forms.Form):
    archivo_excel = forms.FileField(label="Selecciona el archivo de Excel (.xlsx)")


# =========================================================================
#  CLASE BASE PARA IMPORTACIÓN EXCEL
# =========================================================================
class ExcelImportAdmin(ModelAdmin):
    actions = None 
    import_template = "admin/importar_excel.html"
    change_list_template = "admin/carga_masiva_change_list.html"

    model_class = None       
    pk_field_name = None     
    excel_columns = []       

    list_per_page = 25
    list_select_related = True

    def acciones_rh(self, obj):
        app_label = obj._meta.app_label
        model_name = obj._meta.model_name
        editar_url = f"/admin/{app_label}/{model_name}/{obj.pk}/change/"
        eliminar_url = f"/admin/{app_label}/{model_name}/{obj.pk}/delete/"
        
        return format_html(
            '<a href="{}" title="Editar" style="'
            'display: inline-flex !important; align-items: center !important; justify-content: center !important; '
            'width: 26px !important; height: 26px !important; border-radius: 4px !important; margin-right: 6px !important; '
            'background-color: #72a651 !important; color: #ffffff !important; font-weight: bold !important; '
            'text-decoration: none !important; font-size: 14px !important; opacity: 1 !important; line-height: 1 !important;">'
            '&#9998;'
            '</a>'
            '<a href="{}" title="Eliminar" style="'
            'display: inline-flex !important; align-items: center !important; justify-content: center !important; '
            'width: 26px !important; height: 26px !important; border-radius: 4px !important; '
            'background-color: #de3a3a !important; color: #ffffff !important; font-weight: bold !important; '
            'text-decoration: none !important; font-size: 13px !important; opacity: 1 !important; line-height: 1 !important;">'
            '&#10006;'
            '</a>',
            editar_url, eliminar_url
        )
    acciones_rh.short_description = "Acciones"

    # def get_urls(self):
    #     urls = super().get_urls()
    #     custom_urls = [
    #         path('import-excel/', self.admin_site.admin_view(self.import_excel_view), name=f'{self.model_class._meta.app_label}_{self.model_class._meta.model_name}_import_excel' if self.model_class else 'import_excel'),
    #     ]
    #     return custom_urls + urls
    def get_urls(self):
        urls = super().get_urls()
        if not self.model:
            return urls

        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name

        custom_urls = [
            # Cambiamos 'importar-excel-catalogo/' por 'importar-excel/'
            path(
                'importar-excel/', 
                self.admin_site.admin_view(self.import_excel_view), 
                name=f'{app_label}_{model_name}_import_excel'
            ),
        ]
        # Ponemos las custom_urls AL INICIO para que Django las evalúe antes que el ID del objeto
        return custom_urls + urls

    def import_excel_view(self, request):
        if request.method == "POST":
            # Recibimos el archivo directo desde el input del listado
            excel_file = request.FILES.get("excel_file")
            
            if not excel_file:
                messages.error(request, "Por favor, selecciona un archivo válido.")
                return redirect(f"/admin/{self.model_class._meta.app_label}/{self.model_class._meta.model_name}/")

            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, "El archivo debe ser un Excel (.xlsx o .xls).")
                return redirect(f"/admin/{self.model_class._meta.app_label}/{self.model_class._meta.model_name}/")

            try:
                wb = openpyxl.load_workbook(excel_file, data_only=True)
                sheet = wb.active

                success_count = 0
                error_count = 0

                for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                    if not any(row):  
                        continue

                    data = {}
                    for col_idx, col_name in enumerate(self.excel_columns):
                        if col_idx < len(row):
                            data[col_name] = row[col_idx]

                    pk_value = data.get(self.pk_field_name)

                    if pk_value:
                        try:
                            # CASO 1: El registro YA EXISTE en la base de datos -> Actualizamos datos
                            instance = self.model_class.objects.get(**{self.pk_field_name: pk_value})
                            for key, value in data.items():
                                setattr(instance, key, value)
                            instance.save()
                            success_count += 1
                        except self.model_class.DoesNotExist:
                            try:
                                # CASO 2: El ID no existe -> FORZAMOS la creación respetando el ID del Excel
                                nuevo_registro = self.model_class()
                                # Le inyectamos manualmente la llave primaria antes que nada
                                setattr(nuevo_registro, self.pk_field_name, pk_value)
                                
                                # Le asignamos el resto de las columnas del excel
                                for key, value in data.items():
                                    if key != self.pk_field_name:
                                        setattr(nuevo_registro, key, value)
                                
                                # Guardamos de forma explícita en la base de datos
                                nuevo_registro.save()
                                success_count += 1
                            except Exception as e:
                                error_count += 1
                                messages.warning(request, f"Error en fila {row_idx} al forzar ID: {e}")
                    else:
                        # CASO 3: Si por alguna razón el Excel no traía ID, dejamos que la DB genere el consecutivo
                        try:
                            self.model_class.objects.create(**data)
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            messages.warning(request, f"Error en fila {row_idx} (Sin ID): {e}")

                messages.success(request, f"Importación completada. Registros procesados: {success_count}. Errores: {error_count}")
                
            except Exception as e:
                messages.error(request, f"Error crítico al procesar el archivo: {e}")
                
        # Al terminar, o si es un GET accidental, redirige de inmediato a la tabla del catálogo
        return redirect(f"/admin/{self.model_class._meta.app_label}/{self.model_class._meta.model_name}/")


# ==========================================
#   INLINE: CLASIFICACIÓN POR PUESTO
# ==========================================
class ClasificacionPorPuestoInlineForm(forms.ModelForm):
    class Meta:
        model = ClasificacionPorPuesto
        fields = ('id_clasificacion',)
        widgets = {
            'id_clasificacion': forms.Select(attrs={
                'style': 'width: 100% !important; min-width: 100% !important; height: 38px !important; display: block !important;'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 🌟 FILTRO MÁGICO: Limitamos las opciones del combo a solo las específicas ('E') ordenadas alfabéticamente
        self.fields['id_clasificacion'].queryset = CompetenciaClasificacion.objects.filter(tipo='E').order_by('descripcion')

        if self.instance and self.instance.pk:
            valor_actual = self.instance.id_clasificacion_id
            self.fields['id_clasificacion'].widget.value = valor_actual
            self.initial['id_clasificacion'] = valor_actual
            self.instance.__class__.__str__ = lambda self: ""
            self.instance.id_clasificacion = None
        else:
            self.initial['id_clasificacion'] = ""


class ClasificacionPorPuestoInline(TabularInline):
    model = ClasificacionPorPuesto
    form = ClasificacionPorPuestoInlineForm
    extra = 1  # 💡 Cambiado a 1 para que se vea más limpio en el panel de Unfold
    fields = ('id_clasificacion',)


# ==========================================
#   INLINE: CLASIFICACIÓN POR EMPLEADO
# ==========================================
class ClasificacionPorEmpleadoInlineForm(forms.ModelForm):
    nueva_competencia_texto = forms.CharField(
        required=False,
        label="Competencia Exclusiva (Captura libre)",
        widget=forms.TextInput(attrs={
            'style': 'width: 100% !important; min-width: 250px !important; height: 38px !important; padding: 0 10px !important;',
            'placeholder': 'Escribe aquí la competencia solo para este empleado...'
        })
    )

    class Meta:
        model = ClasificacionPorEmpleado
        fields = ('id_clasificacion', 'nueva_competencia_texto', 'motivo')
        widgets = {
            'id_clasificacion': forms.Select(attrs={
                'style': 'width: 100% !important; min-width: 200px !important; height: 38px !important;'
            }),
            'motivo': forms.TextInput(attrs={
                'style': 'width: 100% !important; min-width: 150px !important; height: 38px !important;'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.competencia_exclusiva_id:
            self.initial['nueva_competencia_texto'] = self.instance.competencia_exclusiva.descripcion
        
        if self.instance and self.instance.pk:
            valor_actual = self.instance.id_clasificacion_id
            self.fields['id_clasificacion'].widget.value = valor_actual
            self.initial['id_clasificacion'] = valor_actual
            self.instance.__class__.__str__ = lambda self: ""
            self.instance.id_clasificacion = None
        else:
            self.initial['id_clasificacion'] = ""

    def save(self, commit=True):
        instance = super().save(commit=False)
        texto_competencia = self.cleaned_data.get('nueva_competencia_texto')
        id_clasif = self.cleaned_data.get('id_clasificacion') or instance.id_clasificacion

        if texto_competencia and id_clasif:
            from .models import Competencia
            if instance.competencia_exclusiva:
                comp = instance.competencia_exclusiva
                comp.descripcion = texto_competencia
                comp.id_clasificacion = id_clasif
                comp.save()
            else:
                comp = Competencia.objects.create(
                    id_clasificacion=id_clasif,
                    descripcion=texto_competencia
                )
                instance.competencia_exclusiva = comp
        elif not texto_competencia:
            instance.competencia_exclusiva = None

        if commit:
            instance.save()
        return instance


class ClasificacionPorEmpleadoInline(TabularInline):
    model = ClasificacionPorEmpleado
    form = ClasificacionPorEmpleadoInlineForm
    extra = 1
    fields = ('id_clasificacion', 'nueva_competencia_texto', 'motivo')


# ==========================================
#   INLINE: COMPETENCIAS
# ==========================================
class CompetenciaInlineForm(forms.ModelForm):
    descripcion = forms.CharField(
        widget=forms.TextInput(attrs={
            'style': 'width: 100% !important; min-width: 100% !important; height: 38px !important; display: block !important; padding: 0 10px !important;'
        }),
        required=False,
    )

    class Meta:
        model = Competencia
        fields = ('descripcion',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            valor_actual = self.instance.descripcion
            self.fields['descripcion'].widget.value = valor_actual
            self.initial['descripcion'] = valor_actual
            self.instance.descripcion = ""  
        else:
            self.initial['descripcion'] = ""


class CompetenciaInline(TabularInline):
    model = Competencia
    form = CompetenciaInlineForm
    extra = 3  
    fields = ('descripcion',)


# =========================================================================
#   FORMULARIO PRINCIPAL: MATRIZ CHECKLIST DE SELECCIÓN INTELIGENTE
# =========================================================================
class EmpleadoAdminForm(forms.ModelForm):
    competencias_seleccionadas = forms.ModelMultipleChoiceField(
        queryset=Competencia.objects.none(),
        widget=forms.MultipleHiddenInput(),
        required=False,
        label=""
    )

    class Meta:
        model = Empleado
        fields = '__all__'

        # 🌟 AGREGA ESTA PROPIEDAD AQUÍ ABAJO:
        widgets = {
            'fechaalta': forms.DateInput(
                format='%Y-%m-%d',  # 🌟 Obliga a Django a enviar el dato en formato AAAA-MM-DD
                attrs={'type': 'date'}
            ),
        }    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 🌟 NUEVO: FORZAR ORDENAMIENTO ALFABÉTICO EN LOS COMBOS PRINCIPALES DEL FORMULARIO
        if 'user' in self.fields:
            self.fields['user'].queryset = self.fields['user'].queryset.order_by('username')
        
        if 'id_jefe' in self.fields:
            self.fields['id_jefe'].queryset = Empleado.objects.order_by('nombre_largo')
            
        if 'id_puesto' in self.fields:
            self.fields['id_puesto'].queryset = Puesto.objects.order_by('descripcion')
            
        if 'id_departamento' in self.fields:
            self.fields['id_departamento'].queryset = Departamento.objects.order_by('descripcion')

        if self.instance and self.instance.pk:
            empleado_id = self.instance.pk
            # 1. Obtenemos el ID del puesto de la base de datos física de forma segura
            puesto_id = self.instance.id_puesto_id

            # --- UNIVERSO A: Competencias que le corresponden por su Puesto ---
            clasif_puesto_ids = list(ClasificacionPorPuesto.objects.filter(
                id_puesto_id=puesto_id
            ).values_list('id_clasificacion_id', flat=True))

            competencias_del_puesto_ids = list(Competencia.objects.filter(
                id_clasificacion_id__in=clasif_puesto_ids
            ).values_list('id_competencia', flat=True))

            # --- UNIVERSO B: Competencias que el empleado ya tiene guardadas ---
            competencias_guardadas_ids = list(EmpleadoCompetenciaAsignada.objects.filter(
                id_empleado_id=empleado_id
            ).values_list('id_competencia_id', flat=True))

            # --- UNIFICACIÓN DE AMBOS UNIVERSOS (Igual al UNION de tu SQL) ---
            todas_competencias_ids = list(set(competencias_del_puesto_ids + competencias_guardadas_ids))

            # 2. Reconstruimos el queryset final limpio y ordenado
            queryset_competencias = Competencia.objects.filter(
                id_competencia__in=todas_competencias_ids
            ).select_related('id_clasificacion').order_by('id_clasificacion__descripcion', 'descripcion')

            # 3. Asignamos de forma explícita al campo para desactivar el candado de Django
            self.fields['competencias_seleccionadas'].queryset = queryset_competencias
            self.fields['competencias_seleccionadas'].initial = competencias_guardadas_ids

            # Guardamos para change_view
            self.queryset_competencias_custom = queryset_competencias
            self.competencias_iniciales_custom = competencias_guardadas_ids
        else:
            self.queryset_competencias_custom = Competencia.objects.none()
            self.competencias_iniciales_custom = []


# =========================================================================
#   REGISTRO DE CATÁLOGOS EN EL ADMINISTRADOR
# =========================================================================

class PuestoAdmin(ExcelImportAdmin):
    model_class = Puesto
    pk_field_name = 'id_puesto'
    excel_columns = ['id_puesto', 'descripcion']
    list_display = ('id_puesto', 'descripcion', 'acciones_rh')
    search_fields = ('descripcion',)
    inlines = [ClasificacionPorPuestoInline]

#admin.site.register(Puesto, PuestoAdmin)
admin_site.register(Puesto, PuestoAdmin)

class DepartamentoAdmin(ExcelImportAdmin):
    model_class = Departamento
    pk_field_name = 'id_departamento'
    excel_columns = ['id_departamento', 'descripcion']
    list_display = ('id_departamento', 'descripcion', 'acciones_rh')
    search_fields = ('descripcion',)

@admin.action(description='Enviar Enlaces de evaluación por Correo')
def enviar_enlaces_magicos(modeladmin, request, queryset):
    # 🌟 DETECCIÓN DINÁMICA: 
    # Si el queryset es de "Empleado", usamos los seleccionados.
    # Si es de "Evaluacion", buscamos a todos los empleados activos de la empresa.
    # 🌟 DETECCIÓN DINÁMICA: 
    # Filtramos para que tengan correo electrónico válido Y que el campo se_evalua sea True
    if queryset.model == Empleado:
        empleados = queryset.exclude(CorreoElectronico__isnull=True).exclude(CorreoElectronico='').filter(se_evalua=True)
    else:
        # Viene del catálogo de Evaluaciones -> Mandar a todos los que cumplan con los requisitos
        empleados = Empleado.objects.exclude(CorreoElectronico__isnull=True).exclude(CorreoElectronico='').filter(se_evalua=True)
    
    if not empleados.exists():
        modeladmin.message_user(
            request, 
            "No se encontraron empleados con un Correo Electrónico válido para procesar.", 
            messages.WARNING
        )
        return

    contador_correos = 0
    for empleado in empleados:
        # 1. Crear el token secreto para este empleado
        token = TokenAccesoEvaluacion.objects.create(empleado=empleado)
        
        # 2. Construir la URL exclusiva detectando el sitio automáticamente
        dominio_sitio = request.build_absolute_uri('/')
        url_acceso = f"{dominio_sitio}evaluacion/acceso/{token.id_token}/"
        
        # 3. Redactar el Correo Electrónico (Usando nombre_largo o nombre según tu modelo)
        asunto = "Acceso Exclusivo: Tu Evaluación de Desempeño"
        mensaje = f"Hola {empleado.nombre_largo if hasattr(empleado, 'nombre_largo') else empleado.nombre},\n\n" \
                  f"Para acceder directamente a tu panel de evaluación sin necesidad de contraseña, " \
                  f"haz clic en el siguiente enlace:\n\n" \
                  f"{url_acceso}\n\n" \
                  f"Este enlace expirará en 5 días.\n\n" \
                  f"Saludos cordiales,\nRecursos Humanos."
        
        # 4. Enviar usando la configuración de Gmail SMTP
        send_mail(
            asunto,
            mensaje,
            'l.rodriguez@fruver.com.mx',  # Tu correo configurado en settings.py
            [empleado.CorreoElectronico],
            fail_silently=True,
        )
        contador_correos += 1
        
    modeladmin.message_user(
        request, 
        f"Se generaron los tokens y se enviaron {contador_correos} correos exitosamente."
    )    

#admin.site.register(Departamento, DepartamentoAdmin)
admin_site.register(Departamento, DepartamentoAdmin)
class EmpleadoAdmin(CatalogosOrdenadosAdmin, ExcelImportAdmin):
    form = EmpleadoAdminForm  
    model_class = Empleado
    pk_field_name = 'id_empleado'
    excel_columns = ['id_empleado', 'nombre_largo', 'id_puesto_id', 'id_departamento_id', 'id_jefe_id', 'es_jefe_departamento', 'CorreoElectronico', 'estado_empleado', 'fechaalta', 'se_evalua']
    list_display = ('id_empleado', 'nombre_largo', 'id_puesto', 'id_departamento', 'id_jefe', 'es_jefe_departamento', 'CorreoElectronico', 'estado_empleado', 'fechaalta', 'se_evalua', 'acciones_rh')
    list_filter = ('id_departamento', 'id_puesto', 'es_jefe_departamento', 'CorreoElectronico', 'id_jefe', 'estado_empleado', 'se_evalua')
    search_fields = ('nombre_largo', 'id_puesto__descripcion')
    inlines = []  
    actions = [enviar_enlaces_magicos]
    action_submit_label = "Ejecutar acción"
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        matriz_html = ""
        
        if obj:
            # 1. Instanciamos tu formulario personalizado
            form = EmpleadoAdminForm(instance=obj)
            
            # 🌟 ACCIÓN CLAVE: Forzamos al campo interno a aceptar TODAS las competencias unificadas
            queryset = form.queryset_competencias_custom
            form.fields['competencias_seleccionadas'].queryset = queryset
            
            # 2. Obtenemos el set de IDs guardados utilizando la columna relacional física
            guardados_ids = set(EmpleadoCompetenciaAsignada.objects.filter(
                id_empleado_id=obj.pk
            ).values_list('id_competencia_id', flat=True))

            if queryset.exists():
                matriz_html = '''
                <style>
                    .matriz-unfold-container {
                        width: 100% !important;
                        margin-top: 2rem !important;
                        clear: both !important;
                    }
                </style>
                '''
                
                matriz_html += '<div class="matriz-unfold-container bg-gray-50 dark:bg-zinc-900/40 p-6 rounded-lg border border-gray-200 dark:border-zinc-800">'
                matriz_html += '<h2 class="text-base font-semibold text-gray-900 dark:text-white mb-1">Asignación de Competencias Específicas</h2>'
                matriz_html += '<p class="text-sm text-gray-500 dark:text-zinc-400 mb-6">Palomee las competencias específicas del puesto o libres que formarán parte de la evaluación individual de este colaborador.</p>'
                
                ultima_clasificacion = None

                # 3. Iteramos exactamente sobre el listado del UNION
                for comp in queryset:
                    clasif_nombre = comp.id_clasificacion.descripcion if comp.id_clasificacion else "Competencias Específicas Sueltas"
                    
                    if clasif_nombre != ultima_clasificacion:
                        if ultima_clasificacion is not None:
                            matriz_html += '</div></div>' 
                        
                        matriz_html += f'''
                        <div class="mb-6">
                            <h3 class="text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400 mb-3 border-b border-gray-200 dark:border-zinc-800 pb-2 flex items-center gap-2">
                                <span>📂</span> {clasif_nombre}
                            </h3>
                            <div class="grid grid-cols-1 gap-2">
                        '''
                        ultima_clasificacion = clasif_nombre

                    # 4. Evaluamos si el ID numérico de la competencia iterada está guardado
                    is_checked = comp.id_competencia in guardados_ids
                    checked_str = "checked" if is_checked else ""

                    matriz_html += f'''
                        <label class="flex items-center gap-4 bg-white dark:bg-zinc-800/40 hover:bg-gray-100 dark:hover:bg-zinc-800 px-4 py-3 rounded-md border border-gray-200 dark:border-zinc-800/80 cursor-pointer transition-all w-full block">
                            <input type="checkbox" name="competencias_seleccionadas" value="{comp.id_competencia}" {checked_str} class="rounded border-gray-300 dark:border-zinc-700 text-blue-600 focus:ring-blue-500 h-4 w-4" style="accent-color: #3b82f6; min-width: 16px;">
                            <span class="text-gray-700 dark:text-zinc-300 text-sm font-normal leading-normal">{comp.descripcion}</span>
                        </label>
                    '''

                matriz_html += '</div></div></div>'
            else:
                matriz_html = '<div class="mt-6 bg-gray-50 dark:bg-zinc-900/40 p-4 rounded-lg border border-gray-200 dark:border-zinc-800"><p class="text-sm italic text-gray-400">No hay competencias específicas configuradas para el puesto de este empleado.</p></div>'

        extra_context['matriz_competencias_html'] = mark_safe(matriz_html)
        
        # 🌟 PASO COMPLEMENTARIO OBLIGATORIO PARA UNFOLD:
        # Inyectamos el objeto de formulario procesado en el contexto para que reemplace al predeterminado
        extra_context['adminform'] = admin.helpers.AdminForm(
            form,
            list(self.get_fieldsets(request, obj)),
            self.get_prepopulated_fields(request, obj),
            self.get_readonly_fields(request, obj),
            model_admin=self
        )
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        competencias_post = request.POST.getlist('competencias_seleccionadas')
        competencias_post_ids = [int(pk) for pk in competencias_post if pk.isdigit()]

        # 1. Eliminar desmarcados
        EmpleadoCompetenciaAsignada.objects.filter(id_empleado=obj).exclude(id_competencia_id__in=competencias_post_ids).delete()

        # 2. Guardar nuevos checks marcados
        for comp_id in competencias_post_ids:
            EmpleadoCompetenciaAsignada.objects.get_or_create(id_empleado=obj, id_competencia_id=comp_id)

#admin.site.register(Empleado, EmpleadoAdmin)
admin_site.register(Empleado, EmpleadoAdmin)

class CompetenciaClasificacionAdmin(ExcelImportAdmin):
    model_class = CompetenciaClasificacion
    pk_field_name = 'id_clasificacion'
    excel_columns = ['descripcion', 'tipo']
    list_display = ('id_clasificacion', 'descripcion', 'tipo', 'acciones_rh')
    list_filter = ('descripcion', 'tipo')
    search_fields = ('descripcion',)
    fields = ('descripcion', 'tipo')
    inlines = [CompetenciaInline]

#admin.site.register(CompetenciaClasificacion, CompetenciaClasificacionAdmin)
admin_site.register(CompetenciaClasificacion, CompetenciaClasificacionAdmin)

class CompetenciaAdmin(CatalogosOrdenadosAdmin, ExcelImportAdmin):
    model_class = Competencia
    pk_field_name = 'id_competencia'
    excel_columns = ['id_clasificacion_id', 'descripcion']
    list_display = ('id_competencia', 'id_clasificacion', 'descripcion', 'acciones_rh')
    list_filter = ('descripcion',)  
    search_fields = ('descripcion',)

#admin.site.register(Competencia, CompetenciaAdmin)
admin_site.register(Competencia, CompetenciaAdmin)


class EvaluacionAdmin(ExcelImportAdmin):
    model_class = Evaluacion
    pk_field_name = 'id_evaluacion'
    excel_columns = ['descripcion', 'fecha_inicial', 'fecha_final']
    list_display = ('id_evaluacion', 'descripcion', 'fecha_inicial', 'fecha_final', 'acciones_rh', 'cerrada')
    search_fields = ('descripcion',)
    actions = [enviar_enlaces_magicos]
    action_submit_label = "Ejecutar acción"

#admin.site.register(Evaluacion, EvaluacionAdmin)
admin_site.register(Evaluacion, EvaluacionAdmin)