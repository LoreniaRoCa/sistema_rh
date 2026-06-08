from django.core.management.base import BaseCommand
from django.db import connection, transaction
from rh.models import EmpleadoCompetenciaAsignada, ClasificacionPorPuesto, CompetenciaClasificacion, Competencia

class Command(BaseCommand):
    help = 'Borra de forma segura los datos de las competencias y FUERZA el reinicio de los IDs a 1'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("=== INICIANDO LIMPIEZA DE TABLAS Y REINICIO FORZADO DE IDs ==="))
        
        motor_db = connection.vendor
        modelos = [EmpleadoCompetenciaAsignada, ClasificacionPorPuesto, CompetenciaClasificacion, Competencia]
        
        try:
            with transaction.atomic():
                self.stdout.write("Borrando registros de las tablas...")
                # Borramos los datos mediante el ORM
                EmpleadoCompetenciaAsignada.objects.all().delete()
                ClasificacionPorPuesto.objects.all().delete()
                CompetenciaClasificacion.objects.all().delete()
                Competencia.objects.all().delete()
                
                self.stdout.write(self.style.SUCCESS("✔ Datos eliminados de las 4 tablas."))

                # --- REINICIO DE CONTADORES ---
                with connection.cursor() as cursor:
                    if motor_db == 'postgresql':
                        self.stdout.write("Forzando reinicio de secuencias en PostgreSQL...")
                        
                        for modelo in modelos:
                            nombre_tabla = modelo._meta.db_table
                            # Buscamos el campo llave primaria del modelo (suele ser id_puesto, id_empleado, id, etc.)
                            campo_pk = modelo._meta.pk.name
                            
                            # Explicación: pg_get_serial_sequence obtiene el nombre real y exacto de la secuencia en la BD.
                            # RESTART WITH 1; obliga a que el siguiente INSERT comience estrictamente en 1.
                            sql_reinicio = f"""
                                DO $$ 
                                DECLARE 
                                    seq_name TEXT;
                                BEGIN 
                                    SELECT pg_get_serial_sequence('"{nombre_tabla}"', '{campo_pk}') INTO seq_name;
                                    IF seq_name IS NOT NULL THEN
                                        EXECUTE 'ALTER SEQUENCE ' || seq_name || ' RESTART WITH 1;';
                                    END IF;
                                END $$;
                            """
                            cursor.execute(sql_reinicio)
                            
                    elif motor_db == 'mysql':
                        self.stdout.write("Reiniciando auto_increment en MySQL...")
                        for modelo in modelos:
                            nombre_tabla = modelo._meta.db_table
                            cursor.execute(f"ALTER TABLE {nombre_tabla} AUTO_INCREMENT = 1;")
                            
                    else:  # sqlite
                        self.stdout.write("Reiniciando contadores en SQLite...")
                        tablas_nombres = ", ".join([f"'{m._meta.db_table}'" for m in modelos])
                        cursor.execute(f"UPDATE sqlite_sequence SET seq = 0 WHERE name IN ({tablas_nombres});")

            self.stdout.write(self.style.SUCCESS("✔ ¡Éxito total! Contadores reiniciados a 1 de forma estricta."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[-] Ocurrió un error durante la limpieza: {e}"))