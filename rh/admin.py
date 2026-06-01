from django.db import models  
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
import openpyxl
from unfold.admin import ModelAdmin, TabularInline  
from django.utils.html import format_html
from django.utils.safestring import mark_safe

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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel_view), name=f'{self.model_class._meta.app_label}_{self.model_class._meta.model_name}_import_excel' if self.model_class else 'import_excel'),
        ]
        return custom_urls + urls

    def import_excel_view(self, request):
        if request.method == "POST":
            excel_file = request.FILES.get("excel_file")
            if not excel_file:
                messages.error(request, "Por favor, selecciona un archivo.")
                return redirect(request.path)

            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, "El archivo debe ser un Excel (.xlsx o .xls).")
                return redirect(request.path)

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
                            instance = self.model_class.objects.get(**{self.pk_field_name: pk_value})
                            for key, value in data.items():
                                setattr(instance, key, value)
                            instance.save()
                            success_count += 1
                        except self.model_class.DoesNotExist:
                            try:
                                self.model_class.objects.create(**data)
                                success_count += 1
                            except Exception as e:
                                error_count += 1
                                messages.warning(request, f"Error en fila {row_idx}: {e}")
                    else:
                        try:
                            self.model_class.objects.create(**data)
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            messages.warning(request, f"Error en fila {row_idx}: {e}")

                messages.success(request, f"Importación completada. Registros procesados: {success_count}. Errores: {error_count}")
                return redirect(f"admin:{self.model_class._meta.app_label}_{self.model_class._meta.model_name}_changelist")

            except Exception as e:
                messages.error(request, f"Error crítico al procesar el archivo: {e}")
                return redirect(request.path)

        context = {
            **self.admin_site.each_context(request),
            "title": f"Importar {self.model_class._meta.verbose_name_plural if self.model_class else ''} desde Excel",
            "opts": self.model_class._meta if self.model_class else None,
        }
        return render(request, self.import_template, context)


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
    extra = 2  
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            puesto_id = self.instance.id_puesto_id

            # 1. Obtener clasificaciones asignadas al puesto actual del empleado
            clasif_puesto_ids = list(ClasificacionPorPuesto.objects.filter(
                id_puesto_id=puesto_id
            ).values_list('id_clasificacion_id', flat=True))

            # 2. Obtener la lista de clasificaciones que están siendo ocupadas por CUALQUIER puesto
            todas_clasif_en_uso = list(ClasificacionPorPuesto.objects.values_list('id_clasificacion_id', flat=True))

            # 3. 💡 CORRECCIÓN CRÍTICA: Cambiamos 'ESPECIFICA' por 'E', que es el valor real en tu base de datos
            clasif_especificas = CompetenciaClasificacion.objects.filter(
                tipo='E'
            ).filter(
                models.Q(id_clasificacion__in=clasif_puesto_ids) | 
                ~models.Q(id_clasificacion__in=todas_clasif_en_uso)
            ).distinct()

            clasif_validas_ids = list(clasif_especificas.values_list('id_clasificacion', flat=True))

            # 4. Obtener las competencias específicas resultantes
            if clasif_validas_ids:
                queryset_competencias = Competencia.objects.filter(
                    id_clasificacion_id__in=clasif_validas_ids
                ).distinct().select_related('id_clasificacion').order_by('id_clasificacion__descripcion', 'descripcion')
            else:
                queryset_competencias = Competencia.objects.none()

            self.fields['competencias_seleccionadas'].queryset = queryset_competencias
            
            # Cargar estado previo de los checkboxes guardados en la tabla intermedia
            self.fields['competencias_seleccionadas'].initial = list(EmpleadoCompetenciaAsignada.objects.filter(
                id_empleado=self.instance
            ).values_list('id_competencia_id', flat=True))

            self.queryset_competencias_custom = queryset_competencias
            self.competencias_iniciales_custom = self.fields['competencias_seleccionadas'].initial
        else:
            self.queryset_competencias_custom = Competencia.objects.none()
            self.competencias_iniciales_custom = []


# =========================================================================
#   REGISTRO DE CATÁLOGOS EN EL ADMINISTRADOR
# =========================================================================

class PuestoAdmin(ExcelImportAdmin):
    model_class = Puesto
    pk_field_name = 'id_puesto'
    excel_columns = ['descripcion']
    list_display = ('id_puesto', 'descripcion', 'acciones_rh')
    search_fields = ('descripcion',)
    inlines = [ClasificacionPorPuestoInline]

admin.site.register(Puesto, PuestoAdmin)


class DepartamentoAdmin(ExcelImportAdmin):
    model_class = Departamento
    pk_field_name = 'id_departamento'
    excel_columns = ['descripcion']
    list_display = ('id_departamento', 'descripcion', 'acciones_rh')
    search_fields = ('descripcion',)

admin.site.register(Departamento, DepartamentoAdmin)

class EmpleadoAdmin(CatalogosOrdenadosAdmin, ExcelImportAdmin):
    form = EmpleadoAdminForm  
    model_class = Empleado
    pk_field_name = 'id_empleado'
    excel_columns = ['nombre_largo', 'id_puesto_id', 'id_departamento_id', 'id_jefe_id', 'es_jefe_departamento', 'estado_empleado']
    list_display = ('id_empleado', 'nombre_largo', 'id_puesto', 'id_departamento', 'es_jefe_departamento', 'estado_empleado', 'acciones_rh')
    list_filter = ('id_departamento', 'id_puesto', 'es_jefe_departamento', 'estado_empleado')
    search_fields = ('nombre_largo', 'id_puesto__descripcion')
    inlines = []  

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        matriz_html = ""
        
        if obj:
            form = EmpleadoAdminForm(instance=obj)
            queryset = form.queryset_competencias_custom
            
            # 💡 CORRECCIÓN CRÍTICA: Obtenemos los IDs numéricos exactos guardados para este empleado
            guardados_ids = set(EmpleadoCompetenciaAsignada.objects.filter(
                id_empleado=obj
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

                    # 💡 COMPARACIÓN CORREGIDA: Validamos usando la lista pura de IDs numéricos de la BD
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

admin.site.register(Empleado, EmpleadoAdmin)


class CompetenciaClasificacionAdmin(ExcelImportAdmin):
    model_class = CompetenciaClasificacion
    pk_field_name = 'id_clasificacion'
    excel_columns = ['descripcion', 'tipo']
    list_display = ('id_clasificacion', 'descripcion', 'tipo', 'acciones_rh')
    list_filter = ('descripcion', 'tipo')
    search_fields = ('descripcion',)
    fields = ('descripcion', 'tipo')
    inlines = [CompetenciaInline]

admin.site.register(CompetenciaClasificacion, CompetenciaClasificacionAdmin)


class CompetenciaAdmin(CatalogosOrdenadosAdmin, ExcelImportAdmin):
    model_class = Competencia
    pk_field_name = 'id_competencia'
    excel_columns = ['id_clasificacion_id', 'descripcion']
    list_display = ('id_competencia', 'id_clasificacion', 'descripcion', 'acciones_rh')
    list_filter = ('descripcion',)  
    search_fields = ('descripcion',)

admin.site.register(Competencia, CompetenciaAdmin)


class EvaluacionAdmin(ExcelImportAdmin):
    model_class = Evaluacion
    pk_field_name = 'id_evaluacion'
    excel_columns = ['descripcion', 'fecha_inicial', 'fecha_final']
    list_display = ('id_evaluacion', 'descripcion', 'fecha_inicial', 'fecha_final', 'acciones_rh', 'cerrada')
    search_fields = ('descripcion',)

admin.site.register(Evaluacion, EvaluacionAdmin)