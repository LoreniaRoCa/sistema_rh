# ==========================================
# SECCIÓN DE IMPORTS CORREGIDA
# ==========================================
import openpyxl  
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side  

from django.db.models import Avg, Q 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps 
from django.http import HttpResponse
# 💡 INCLUSIÓN: Importamos el nuevo modelo de la tabla intermedia
from .models import (
    Empleado, CompetenciaClasificacion, Competencia, Evaluacion, 
    EvaluacionDet, EvaluacionComentario, EmpleadoCompetenciaAsignada
)
from django.db import connection
from django.utils import timezone

@login_required
def panel_evaluacion_view(request, subordinado_id=None):
    try:
        usuario_logueado = Empleado.objects.get(user=request.user)
    except Empleado.DoesNotExist:
        messages.error(request, "Tu usuario no está vinculado a un registro de Empleado.")
        return redirect('admin:index')

    evaluacion_activa = Evaluacion.objects.filter().last()
    if not evaluacion_activa:
        context = {'error_mensaje': "No hay evaluaciones configuradas en este momento."}
        return render(request, 'evaluaciones/panel_evaluacion.html', context)

    if subordinado_id:
        empleado_a_evaluar = get_object_or_404(Empleado, id_empleado=subordinado_id)
        es_autoevaluacion = False
    else:
        empleado_a_evaluar = usuario_logueado
        es_autoevaluacion = True

    tipo_evaluador = 'E' if es_autoevaluacion else 'J'

    # =========================================================================
    # 💡 NUEVA ESTRUCTURA DE EXTRACCIÓN INTELIGENTE DE COMPETENCIAS
    # =========================================================================
    
    # 1. Traer de forma automática todas las Competencias Globales (Tipo G)
    competencias_globales_ids = list(Competencia.objects.filter(
        id_clasificacion__tipo='G'
    ).values_list('id_competencia', flat=True))

    # 2. Traer ÚNICAMENTE las Competencias Específicas palomeadas en tu nueva tabla intermedia
    competencias_asignadas_ids = list(EmpleadoCompetenciaAsignada.objects.filter(
        id_empleado=empleado_a_evaluar
    ).values_list('id_competencia_id', flat=True))

    # 3. Consolidar ambos universos en una única lista limpia de IDs sin duplicados
    ids_competencias_validas = list(set(competencias_globales_ids + competencias_asignadas_ids))

    # 4. Pedir al ORM los registros reales ordenados para armar la interfaz
    competencias_reales = Competencia.objects.filter(
        id_competencia__in=ids_competencias_validas
    ).select_related('id_clasificacion')

    # =========================================================================
    # 2. RESPUESTAS PREVIAS Y CALIFICACIONES
    # =========================================================================
    respuestas_previos = EvaluacionDet.objects.filter(
        id_evaluacion=evaluacion_activa,
        id_empleado=empleado_a_evaluar,
        tipo=tipo_evaluador
    )
    ya_contestado = respuestas_previos.exists()
    
    notes_dict_data = {}
    for r in respuestas_previos:
        if r.id_competencia_id is not None:
            notes_dict_data[int(r.id_competencia_id)] = int(r.calificacion)
    notas_guardadas = notes_dict_data

    comentarios_previos = EvaluacionComentario.objects.filter(
        id_evaluacion=evaluacion_activa,
        id_empleado=empleado_a_evaluar,
        tipo_evaluador=tipo_evaluador
    )
    comentarios_dict = {c.tipo_bloque: c for c in comentarios_previos}
    comentario_g = comentarios_dict.get('G')
    comentario_e = comentarios_dict.get('E')

    # =========================================================================
    # SUBORDINADOS ASOCIADOS DIRECTAMENTE
    # =========================================================================
    subordinados_pendientes = []
    equipo = Empleado.objects.filter(id_jefe_id=usuario_logueado.id_empleado).exclude(id_empleado=usuario_logueado.id_empleado)
    
    for miembro in equipo:
        ya_evaluado_por_jefe = EvaluacionDet.objects.filter(
            id_evaluacion=evaluacion_activa,
            id_empleado=miembro,
            tipo='J'
        ).exists()
        
        subordinados_pendientes.append({
            'empleado': miembro,
            'estatus': 'Contestado' if ya_evaluado_por_jefe else 'Pendiente'
        })

    # =========================================================================
    # 3. CONSTRUCCIÓN DE LA ESTRUCTURA PARA EL HTML
    # =========================================================================
    mapa_clasificaciones = {}

    for comp in competencias_reales:
        clasif = comp.id_clasificacion
        if clasif.id_clasificacion not in mapa_clasificaciones:
            mapa_clasificaciones[clasif.id_clasificacion] = {
                'clasificacion': clasif,        
                'competencia_list': []          
            }
        mapa_clasificaciones[clasif.id_clasificacion]['competencia_list'].append(comp)

    clasificaciones_generales = []
    clasificaciones_especificas = []

    for clasif_id, item in mapa_clasificaciones.items():
        clasif_obj = item['clasificacion']
        lista_comps = item['competencia_list']
        
        valores_calificaciones = [
            notas_guardadas[c.id_competencia] 
            for c in lista_comps if c.id_competencia in notas_guardadas
        ]
        promedio = sum(valores_calificaciones) / len(valores_calificaciones) if valores_calificaciones else 0
        item['promedio'] = round(promedio, 2)

        tipo_codigo = str(clasif_obj.tipo).strip().upper()

        if tipo_codigo == 'G':
            clasificaciones_generales.append(item)
        elif tipo_codigo == 'E':
            clasificaciones_especificas.append(item)

    clasificaciones_generales = sorted(clasificaciones_generales, key=lambda x: x['clasificacion'].descripcion)
    clasificaciones_especificas = sorted(clasificaciones_especificas, key=lambda x: x['clasificacion'].descripcion)

    context = {
        'evaluacion': evaluacion_activa,
        'evaluacion_cerrada': getattr(evaluacion_activa, 'cerrada', False), 
        'empleado': empleado_a_evaluar,         
        'usuario_logueado': usuario_logueado,   
        'clasificaciones_generales': clasificaciones_generales,
        'clasificaciones_especificas': clasificaciones_especificas,
        'ya_autoevaluado': ya_contestado, 
        'notas_guardadas': notas_guardadas,
        'comentario_g': comentario_g,
        'comentario_e': comentario_e,
        'subordinados': subordinados_pendientes,
        'es_autoevaluacion': es_autoevaluacion,
    }
    return render(request, 'evaluaciones/panel_evaluacion.html', context)

@login_required
def guardar_evaluacion_view(request):
    if request.method == "POST":
        try:
            evaluador = Empleado.objects.get(user=request.user)
        except Empleado.DoesNotExist:
            messages.error(request, "Error: Tu usuario no está ligado a un empleado.")
            return redirect('admin:index')

        evaluado_id = request.POST.get("evaluado_id")
        evaluado = get_object_or_404(Empleado, id_empleado=evaluado_id)

        evaluacion_activa = Evaluacion.objects.filter().last()
        if not evaluacion_activa:
            messages.error(request, "No hay una evaluación activa en este momento.")
            return redirect('admin:index')

        if getattr(evaluacion_activa, 'cerrada', False):
            messages.error(request, "El periodo de evaluaciones ha sido cerrado. No se permiten más modificaciones.")
            return redirect('panel_evaluacion')

        if str(evaluador.id_empleado) == str(evaluado.id_empleado):
            tipo_evaluador = 'E'
        else:
            tipo_evaluador = 'J'

        # 1. GUARDAR RETROALIMENTACIÓN DE COMPETENCIAS GENERALES
        fortalezas_gen = request.POST.get("fortalezas_generales", "").strip()
        oportunidades_gen = request.POST.get("oportunidades_generales", "").strip()
        
        EvaluacionComentario.objects.update_or_create(
            id_evaluacion=evaluacion_activa,
            id_empleado=evaluado,
            tipo_bloque='G',       
            tipo_evaluador=tipo_evaluador,
            defaults={
                'fortalezas': Exam_clean_text(fortalezas_gen),
                'areas_oportunidad': Exam_clean_text(oportunidades_gen)
            }
        )

        # 2. GUARDAR RETROALIMENTACIÓN DE COMPETENCIAS ESPECÍFICAS
        fortalezas_esp = request.POST.get("fortalezas_especificas", "").strip()
        oportunidades_esp = request.POST.get("oportunidades_especificas", "").strip()
        
        EvaluacionComentario.objects.update_or_create(
            id_evaluacion=evaluacion_activa,
            id_empleado=evaluado,
            tipo_bloque='E',       
            tipo_evaluador=tipo_evaluador,
            defaults={
                'fortalezas': Exam_clean_text(fortalezas_esp),
                'areas_oportunidad': Exam_clean_text(oportunidades_esp)
            }
        )

        # 3. GUARDAR CALIFICACIONES NUMÉRICAS
        for key, value in request.POST.items():
            if key.startswith("nota_") and value:
                competencia_id = key.split("_")[1]
                competencia = get_object_or_404(Competencia, id_competencia=competencia_id)
                
                EvaluacionDet.objects.update_or_create(
                    id_evaluacion=evaluacion_activa,
                    id_empleado=evaluado,
                    id_competencia=competencia,
                    tipo=tipo_evaluador,
                    defaults={'calificacion': int(value)} 
                )

        nombre_evaluacion = evaluacion_activa.descripcion if evaluacion_activa.descripcion else "Evaluación de Desempeño"

        messages.success(
            request, 
            f'La evaluación "{nombre_evaluacion}" de {evaluado.nombre_largo} se guardó correctamente.'
        )
        
        return redirect('panel_evaluacion')

    return redirect('panel_evaluacion')

def Exam_clean_text(text):
    return text if text != "" else None

@login_required
def resumen_evaluaciones_view(request):
    evaluacion_activa = Evaluacion.objects.filter().last()
    matriz_resultados = []
    
    if evaluacion_activa:
        resultados_db = EvaluacionDet.objects.filter(
            id_evaluacion=evaluacion_activa
        ).values(
            'id_empleado__id_empleado', 
            'id_empleado__nombre_largo'
        ).annotate(
            avg_auto_gen=Avg('calificacion', filter=Q(tipo='E', id_competencia__id_clasificacion__tipo='G')),
            avg_auto_esp=Avg('calificacion', filter=Q(tipo='E', id_competencia__id_clasificacion__tipo='E')),
            avg_jefe_gen=Avg('calificacion', filter=Q(tipo='J', id_competencia__id_clasificacion__tipo='G')),
            avg_jefe_esp=Avg('calificacion', filter=Q(tipo='J', id_competencia__id_clasificacion__tipo='E'))
        ).order_by('id_empleado__nombre_largo')

        for registro in resultados_db:
            auto_gen = registro['avg_auto_gen'] or 0.0
            auto_esp = registro['avg_auto_esp'] or 0.0
            jefe_gen = registro['avg_jefe_gen'] or 0.0
            jefe_esp = registro['avg_jefe_esp'] or 0.0
            
            promedio_auto = (auto_gen + auto_esp) / 2 if (auto_gen or auto_esp) else 0.0
            promedio_jefe = (jefe_gen + jefe_esp) / 2 if (jefe_gen or jefe_esp) else 0.0
            
            if promedio_auto > 0 and promedio_jefe > 0:
                promedio_total = (promedio_auto + promedio_jefe) / 2
            else:
                promedio_total = promedio_auto or promedio_jefe or 0.0
                
            if promedio_total is None:
                gratificacion = "Sin evaluar"
            elif 1.0 <= promedio_total <= 1.5:
                gratificacion = "0"
            elif 1.6 <= promedio_total <= 1.9:
                gratificacion = "15 días"
            elif 2.0 <= promedio_total <= 2.9:
                gratificacion = "1 mes"
            elif 3.0 <= promedio_total <= 3.9:
                gratificacion = "2 meses"
            elif 4.0 <= promedio_total <= 5.0:
                gratificacion = "3 meses"
            else:
                gratificacion = "Fuera de rango"
                
            matriz_resultados.append({
                'nombre_largo': registro['id_empleado__nombre_largo'],
                'auto_gen': round(auto_gen, 2),
                'auto_esp': round(auto_esp, 2),
                'promedio_auto': round(promedio_auto, 2),
                'jefe_gen': round(jefe_gen, 2),
                'jefe_esp': round(jefe_esp, 2),
                'promedio_jefe': round(promedio_jefe, 2),
                'promedio_total': round(promedio_total, 2),
                'gratificacion': gratificacion,            
            })
            

    context = {
        'evaluacion': evaluacion_activa,
        'matriz_resultados': matriz_resultados
    }
    return render(request, 'evaluaciones/resumen_evaluaciones.html', context)

@login_required
def descargar_plantilla_excel(request, model_name):
    try:
        model = apps.get_model('rh', model_name)
    except LookupError:
        return HttpResponse("Modelo no encontrado", status=404)

    columnas = [field.name for field in model._meta.fields if field.name != 'id' and not field.auto_created]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Plantilla {model._meta.verbose_name_plural}"

    font_header = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    fill_header = PatternFill(start_color='096446', end_color='096446', fill_type='solid')

    for col_num, column_title in enumerate(columnas, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = column_title
        cell.font = font_header
        cell.fill = fill_header
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = max(len(column_title) + 5, 15)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=plantilla_{model_name}.xlsx'
    
    wb.save(response)
    return response

@login_required
def exportar_resumen_excel(request):
    evaluacion_activa = Evaluacion.objects.filter().last()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado"
    
    ws.views.sheetView[0].showGridLines = True
    
    font_titulo = Font(name='Arial', size=16, bold=True, color='0F172A')
    font_subtitulo = Font(name='Arial', size=10, italic=True, color='475569')
    font_header_grupo = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    font_header_sub = Font(name='Arial', size=10, bold=True, color='1E293B')
    font_datos = Font(name='Arial', size=10)
    font_destacada = Font(name='Arial', size=10, bold=True)
    
    fill_titulo_seccion = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid') 
    fill_auto = PatternFill(start_color='065F46', end_color='065F46', fill_type='solid') 
    fill_jefe = PatternFill(start_color='1E40AF', end_color='1E40AF', fill_type='solid') 
    fill_sub_headers = PatternFill(start_color='F1F5F9', end_color='F1F5F9', fill_type='solid') 
    fill_total = PatternFill(start_color='E2E8F0', end_color='E2E8F0', fill_type='solid') 
    fill_gratificacion = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid') 
    
    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    align_left = Alignment(horizontal='left', vertical='center')
    
    border_delgado = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    descripcion_eval = evaluacion_activa.descripcion if evaluacion_activa else "Evaluación de Desempeño"
    ws['A1'] = "Consolidado de Resultados de Evaluación"
    ws['A1'].font = font_titulo
    ws['A2'] = f"Monitoreo general de la: {descripcion_eval} | Fecha de extracción: {timezone.now().strftime('%d/%m/%Y')}"
    ws['A2'].font = font_subtitulo
    
    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 18
    
    ws.merge_cells('A4:A5')
    ws['A4'] = "Empleado"
    
    ws.merge_cells('B4:D4')
    ws['B4'] = "Autoevaluación"
    
    ws.merge_cells('E4:G4')
    ws['E4'] = "Evaluación Jefe"
    
    ws.merge_cells('H4:H5')
    ws['H4'] = "Promedio Total"
    
    ws.merge_cells('I4:I5')
    ws['I4'] = "Gratificación"
    
    headers_superiores = {
        'A4': fill_titulo_seccion, 'B4': fill_auto, 'C4': fill_auto, 'D4': fill_auto,
        'E4': fill_jefe, 'F4': fill_jefe, 'G4': fill_jefe, 'H4': fill_titulo_seccion, 'I4': fill_titulo_seccion
    }
    ws.row_dimensions[4].height = 26
    for celda, fill in headers_superiores.items():
        ws[celda].fill = fill
        ws[celda].font = font_header_grupo
        ws[celda].alignment = align_center
        ws[celda].border = border_delgado
        
    sub_headers = ["Prom. Generales", "Prom. Específicas", "Prom. Auto", "Prom. Generales", "Prom. Específicas", "Prom. Jefe"]
    for i, texto in enumerate(sub_headers, start=2): 
        celda = ws.cell(row=5, column=i, value=texto)
        celda.fill = fill_sub_headers
        celda.font = font_header_sub
        celda.alignment = align_center
        celda.border = border_delgado
    ws.row_dimensions[5].height = 22
    
    for col in ['A', 'H', 'I']:
        ws[f'{col}5'].border = border_delgado
        ws[f'{col}5'].fill = fill_sub_headers

    if evaluacion_activa:
        resultados_db = EvaluacionDet.objects.filter(
            id_evaluacion=evaluacion_activa
        ).values(
            'id_empleado__nombre_largo'
        ).annotate(
            avg_auto_gen=Avg('calificacion', filter=Q(tipo='E', id_competencia__id_clasificacion__tipo='G')),
            avg_auto_esp=Avg('calificacion', filter=Q(tipo='E', id_competencia__id_clasificacion__tipo='E')),
            avg_jefe_gen=Avg('calificacion', filter=Q(tipo='J', id_competencia__id_clasificacion__tipo='G')),
            avg_jefe_esp=Avg('calificacion', filter=Q(tipo='J', id_competencia__id_clasificacion__tipo='E'))
        ).order_by('id_empleado__nombre_largo')

        row_num = 6
        for registro in resultados_db:
            auto_gen = registro['avg_auto_gen'] or 0.0
            auto_esp = registro['avg_auto_esp'] or 0.0
            jefe_gen = registro['avg_jefe_gen'] or 0.0
            jefe_esp = registro['avg_jefe_esp'] or 0.0
            
            promedio_auto = (auto_gen + auto_esp) / 2 if (auto_gen or auto_esp) else 0.0
            promedio_jefe = (jefe_gen + jefe_esp) / 2 if (jefe_gen or jefe_esp) else 0.0
            
            if promedio_auto > 0 and promedio_jefe > 0:
                promedio_total = (promedio_auto + promedio_jefe) / 2
            else:
                promedio_total = promedio_auto or promedio_jefe or 0.0
                
            if promedio_total <= 0:
                gratificacion = "Sin evaluar"
            elif promedio_total < 1.6:
                gratificacion = "0"
            elif promedio_total < 2.0:
                gratificacion = "15 días"
            elif promedio_total < 3.0:
                gratificacion = "1 mes"
            elif promedio_total < 4.0:
                gratificacion = "2 meses"
            elif promedio_total <= 5.0:
                gratificacion = "3 meses"
            else:
                gratificacion = "Fuera de rango"

            ws.cell(row=row_num, column=1, value=registro['id_empleado__nombre_largo']).alignment = align_left
            ws.cell(row=row_num, column=2, value=round(auto_gen, 2)).number_format = '0.00'
            ws.cell(row=row_num, column=3, value=round(auto_esp, 2)).number_format = '0.00'
            ws.cell(row=row_num, column=4, value=round(promedio_auto, 2)).number_format = '0.00'
            ws.cell(row=row_num, column=5, value=round(jefe_gen, 2)).number_format = '0.00'
            ws.cell(row=row_num, column=6, value=round(jefe_esp, 2)).number_format = '0.00'
            ws.cell(row=row_num, column=7, value=round(promedio_jefe, 2)).number_format = '0.00'
            ws.cell(row=row_num, column=8, value=round(promedio_total, 2)).number_format = '0.00'
            ws.cell(row=row_num, column=9, value=gratificacion).alignment = align_center

            for col_idx in range(1, 10):
                cell = ws.cell(row=row_num, column=col_idx)
                cell.font = font_datos
                cell.border = border_delgado
                if col_idx in [2, 3, 4, 5, 6, 7, 8]:
                    cell.alignment = align_center
                
                if col_idx in [4, 7]:
                    cell.font = font_destacada
                if col_idx == 8: 
                    cell.font = Font(name='Arial', size=10, bold=True, color='0F172A')
                    cell.fill = fill_total
                if col_idx == 9: 
                    cell.font = font_destacada
                    cell.fill = fill_gratificacion

            ws.row_dimensions[row_num].height = 20
            row_num += 1

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
    ws.column_dimensions['A'].width = 38 

    nombre_archivo = f"Consolidado_Resultados_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f"attachment; filename={nombre_archivo}"
    
    wb.save(response)
    return response

# def dashboard_evaluaciones(request):
#     departamentos_data = []
    
#     # Ejecutamos tu nueva vista de Supabase
#     with connection.cursor() as cursor:
#         cursor.execute("""
#             SELECT 
#                 departamento, 
#                 jefe, 
#                 numempleados, 
#                 autoevaluados, 
#                 evaluados 
#             FROM vista_dashboard_departamentos
#         """)
#         rows = cursor.fetchall()
        
#         for row in rows:
#             num_empleados = int(row[2])
#             auto_contestadas = int(row[3])
#             jefe_contestadas = int(row[4])
            
#             # Cálculo de pendientes
#             auto_pendientes = num_empleados - auto_contestadas
#             jefe_pendientes = num_empleados - jefe_contestadas
            
#             # Cálculo de porcentajes para las barras de progreso
#             auto_pct = round((auto_contestadas / num_empleados * 100), 1) if num_empleados > 0 else 0.0
#             jefe_pct = round((jefe_contestadas / num_empleados * 100), 1) if num_empleados > 0 else 0.0
            
#             departamentos_data.append({
#                 'nombre': row[0],
#                 'jefe': row[1],
#                 'total_empleados': num_empleados,
#                 'auto_contestadas': auto_contestadas,
#                 'auto_por_contestar': auto_pendientes,
#                 'auto_pct': auto_pct,
#                 'jefe_contestadas': jefe_contestadas,
#                 'jefe_por_contestar': jefe_pendientes,
#                 'jefe_pct': jefe_pct,
#             })

#     # --- CÁLCULO DE KPIs GLOBALES (Sumatorias de todas las filas) ---
#     total_global_empleados = sum(d['total_empleados'] for d in departamentos_data)
#     total_auto_global = sum(d['auto_contestadas'] for d in departamentos_data)
#     total_jefe_global = sum(d['jefe_contestadas'] for d in departamentos_data)

#     global_kpis = {
#         'total_empleados': total_global_empleados,
#         'auto_contestadas': total_auto_global,
#         'auto_porcentaje': round((total_auto_global / total_global_empleados * 100), 1) if total_global_empleados > 0 else 0.0,
#         'jefe_contestadas': total_jefe_global,
#         'jefe_porcentaje': round((total_jefe_global / total_global_empleados * 100), 1) if total_global_empleados > 0 else 0.0,
#     }

#     context = {
#         'global_kpis': global_kpis,
#         'departamentos_dashboard': departamentos_data,
#     }
#     return render(request, 'admin/index.html', context)        