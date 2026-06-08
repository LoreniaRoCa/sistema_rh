import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from rh.models import (
    Empleado, 
    Puesto, 
    CompetenciaClasificacion, 
    Competencia, 
    ClasificacionPorPuesto, 
    EmpleadoCompetenciaAsignada
)

class Command(BaseCommand):
    help = 'Importa la matriz de competencias de forma masiva y optimizada en memoria.'

    def handle(self, *args, **options):
        archivo_excel = os.path.join(os.getcwd(), 'Resultado.xlsx')

        if not os.path.exists(archivo_excel):
            self.stdout.write(self.style.ERROR(f"No se encontró el archivo '{archivo_excel}'."))
            return

        self.stdout.write(self.style.WARNING("=== CArGANDO DATOS DEL EXCEL ==="))
        df = pd.read_excel(archivo_excel)
        df.columns = [c.strip() for c in df.columns]
        
        total_filas = len(df)
        self.stdout.write(self.style.SUCCESS(f"✔ Archivo leído con éxito. Total de filas a procesar: {total_filas}"))

        # --- OPTIMIZACIÓN EN MEMORIA ---
        # Traemos los puestos y empleados existentes a diccionarios para no saturar la BD con miles de .get()
        self.stdout.write(self.style.WARNING("Mapeando empleados y puestos en memoria para velocidad..."))
        dict_puestos = {p.id_puesto: p for p in Puesto.objects.all()}
        dict_empleados = {e.id_empleado: e for e in Empleado.objects.all()}

        self.stdout.write(self.style.WARNING("=== INICIANDO TRANSACCIÓN EN BASE DE DATOS ==="))

        try:
            with transaction.atomic():
                clasificaciones_creadas = 0
                competencias_creadas = 0
                puestos_vinculados = 0
                empleados_vinculados = 0

                for idx, row in df.iterrows():
                    num_fila = idx + 2
                    nom_clasificacion = str(row['Clasificación']).strip().upper()
                    desc_competencia = str(row['Competencia']).strip()
                    id_val_empleado = int(row['idempleado'])
                    id_val_puesto = int(row['idpuesto'])

                    if not nom_clasificacion or nom_clasificacion == "NAN" or not desc_competencia or desc_competencia == "NAN":
                        continue

                    # Imprimir progreso cada 20 filas para saber que sigue vivo
                    if num_fila % 20 == 0 or num_fila == total_filas:
                        self.stdout.write(f"Procesando fila {num_fila} de {total_filas}...")

                    # 1. Clasificación
                    clasificacion_obj, creada_clas = CompetenciaClasificacion.objects.get_or_create(
                        descripcion=nom_clasificacion
                    )
                    if creada_clas:
                        clasificaciones_creadas += 1

                    # 2. Competencia
                    competencia_obj, creada_comp = Competencia.objects.get_or_create(
                        descripcion=desc_competencia,
                        id_clasificacion=clasificacion_obj
                    )
                    if creada_comp:
                        competencias_creadas += 1

                    # 3. Vínculo Puesto -> Clasificación
                    puesto_obj = dict_puestos.get(id_val_puesto)
                    if puesto_obj:
                        _, creado_pue_clas = ClasificacionPorPuesto.objects.get_or_create(
                            id_puesto=puesto_obj,
                            id_clasificacion=clasificacion_obj
                        )
                        if creado_pue_clas:
                            puestos_vinculados += 1
                    else:
                        self.stdout.write(self.style.ERROR(f"Fila {num_fila}: El id_puesto {id_val_puesto} no existe en la BD."))

                    # 4. Vínculo Empleado -> Competencia
                    empleado_obj = dict_empleados.get(id_val_empleado)
                    if empleado_obj:
                        _, creado_emp_comp = EmpleadoCompetenciaAsignada.objects.get_or_create(
                            id_empleado=empleado_obj,
                            id_competencia=competencia_obj
                        )
                        if creado_emp_comp:
                            empleados_vinculados += 1
                    else:
                        self.stdout.write(self.style.ERROR(f"Fila {num_fila}: El id_empleado {id_val_empleado} no existe en la BD."))

                # Resumen
                self.stdout.write(self.style.SUCCESS("\n=== ¡IMPORTACIÓN COMPLETADA EXITOSAMENTE! ==="))
                self.stdout.write(self.style.SUCCESS(f"✔ Clasificaciones nuevas: {clasificaciones_creadas}"))
                self.stdout.write(self.style.SUCCESS(f"✔ Competencias nuevas: {competencias_creadas}"))
                self.stdout.write(self.style.SUCCESS(f"✔ Vínculos Puesto-Clasificación: {puestos_vinculados}"))
                self.stdout.write(self.style.SUCCESS(f"✔ Competencias asignadas a Empleados: {empleados_vinculados}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n[-] Error durante la ejecución: {e}"))
            self.stdout.write(self.style.ERROR("Si el proceso se congela, reinicia el servicio de tu Base de Datos para liberar bloqueos."))