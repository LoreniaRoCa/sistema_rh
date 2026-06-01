# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.auth.models import User

class Competencia(models.Model):
    id_competencia = models.AutoField(primary_key=True)
# =========================================================================
    # EL TRUCO PARA EL NOMBRE DEL CAMPO: Agregamos verbose_name="Clasificación"
    # =========================================================================
    id_clasificacion = models.ForeignKey(
        'CompetenciaClasificacion', 
        models.DO_NOTHING, 
        db_column='id_clasificacion',
        verbose_name="Clasificación"  # <-- Así aparecerá en el formulario de agregar
    )
    descripcion = models.TextField()

    def __str__(self):
        return self.descripcion

    class Meta:
        managed = True
        db_table = 'competencia'
        verbose_name = "Competencia"
        verbose_name_plural = "Competencias"


class CompetenciaClasificacion(models.Model):
    id_clasificacion = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=150)

    # 1. Definimos las opciones que verá el usuario
    OPCIONES_CLASIFICACION = [
        ('G', 'General'),
        ('E', 'Específica'),
    ]
    tipo = models.CharField(
        max_length=1,
        choices=OPCIONES_CLASIFICACION,   # Esto lo convierte en una lista desplegable
        default='G',              # Por defecto estará seleccionado "General"
        verbose_name="Tipo Competencia"
    )

# =========================================================================
    # EL TRUCO PARA EL MENÚ DESPLEGABLE: Muestra la descripción real
    # =========================================================================
    def __str__(self):
        return self.descripcion

    class Meta:
        managed = True
        db_table = 'competencia_clasificacion'
        verbose_name = "Competencia clasificación"          
        verbose_name_plural = "Competencia Clasificaciones"   

class Departamento(models.Model):
    id_departamento = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=150)

    class Meta:
        managed = True
        db_table = 'departamento'

    def __str__(self):
        return self.descripcion

class Empleado(models.Model):
    id_empleado = models.AutoField(primary_key=True)

    # 2. El campo mágico: Relación uno a uno.
    # Un empleado pertenece a un usuario, un usuario pertenece a un empleado.
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL,  # Si borran el usuario, el empleado no se borra (queda en NULL)
        null=True, 
        blank=True, 
        verbose_name="Usuario de Sistema"
    )
    nombre_largo = models.CharField(max_length=255)
    
    # Un empleado pertenece a un departamento (puede omitirse temporalmente)
    id_departamento = models.ForeignKey(
        'Departamento', 
        models.SET_NULL, 
        db_column='id_departamento', 
        blank=True, 
        null=True
    )
    
    # AUTORELACIÓN: Un empleado reporta a otro empleado (su jefe directo)
    id_jefe = models.ForeignKey(
        'self', 
        models.SET_NULL, 
        db_column='id_jefe', 
        blank=True, 
        null=True,
        verbose_name="Jefe Inmediato"
    )
    
    id_puesto = models.ForeignKey(
        'Puesto', 
        models.DO_NOTHING, 
        db_column='id_puesto'
    )
    
    # LA SOLUCIÓN: Saber si lidera el departamento al que está asignado
    es_jefe_departamento = models.BooleanField(
        default=False, 
        verbose_name="¿Es la cabeza de este departamento?"
    )
    # 1. Definimos las opciones que verá el usuario
    OPCIONES_ESTADO = [
        ('A', 'Alta'),
        ('B', 'Baja'),
    ]
    estado_empleado = models.CharField(
        max_length=1,
        choices=OPCIONES_ESTADO,   # Esto lo convierte en una lista desplegable
        default='A',              # Por defecto estará seleccionado "Alta"
        verbose_name="Estado del Empleado"
    )
    class Meta:
        managed = True
        db_table = 'empleado'

    def __str__(self):
        return self.nombre_largo

class Evaluacion(models.Model):
    id_evaluacion = models.CharField(primary_key=True, max_length=20)
    descripcion = models.CharField(max_length=255)
    fecha_inicial = models.DateField()
    fecha_final = models.DateField()
    # NUEVO CAMPO: Indica si el periodo de evaluación ya fue clausurado por el administrador
    cerrada = models.BooleanField(default=False, verbose_name="¿Evaluación Cerrada?")
    class Meta:
        managed = True
        db_table = 'evaluacion'
        # LOS CAMBIOS CLAVE:
        verbose_name = "Evaluación"          # Cómo se dice en singular
        verbose_name_plural = "Evaluaciones" # Cómo se mostrará en el menú de la izquierda


class EvaluacionDet(models.Model):
    pk = models.CompositePrimaryKey('id_evaluacion', 'id_competencia', 'id_empleado', 'tipo')
    id_evaluacion = models.ForeignKey(Evaluacion, models.DO_NOTHING, db_column='id_evaluacion')
    id_competencia = models.ForeignKey(Competencia, models.DO_NOTHING, db_column='id_competencia')
    id_empleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='id_empleado')
    calificacion = models.IntegerField(blank=True, null=True)
    # Definimos las opciones válidas
    TIPO_EVALUADOR_CHOICES = [
        ('E', 'Empleado (Autoevaluación)'),
        ('J', 'Jefe (Evaluación a Colaborador)'),
    ]

    # ... tus otros campos ...

    tipo = models.CharField(
        max_length=1,
        choices=TIPO_EVALUADOR_CHOICES,
        blank=False,  # No permite que se envíe vacío en formularios
        null=False    # No permite valores NULL en la base de datos
    )

    class Meta:
        managed = True
        db_table = 'evaluacion_det'


class Puesto(models.Model):
    id_puesto = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=150)

    class Meta:
        managed = True
        db_table = 'puesto'

    # ADICIONA ESTA FUNCIÓN AL FINAL DE LA CLASE PUESTO
    def __str__(self):
        return self.descripcion

class EvaluacionComentario(models.Model):
    TIPO_BLOQUE_CHOICES = [
        ('G', 'Generales'),
        ('E', 'Específicas')
    ]
    TIPO_EVALUADOR_CHOICES = [
        ('E', 'Empleado (Autoevaluación)'),
        ('J', 'Jefe (Evaluación a Colaborador)')
    ]

    id_evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE)
    id_empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    tipo_bloque = models.CharField(max_length=1, choices=TIPO_BLOQUE_CHOICES)
    tipo_evaluador = models.CharField(max_length=1, choices=TIPO_EVALUADOR_CHOICES)
    fortalezas = models.TextField(blank=True, null=True)
    areas_oportunidad = models.TextField(blank=True, null=True)

    class Meta:
        # Esto evita duplicados: solo un registro por evaluación, empleado, bloque y rol
        unique_together = ('id_evaluacion', 'id_empleado', 'tipo_bloque', 'tipo_evaluador')

    def __str__(self):
        return f"Comentarios {self.tipo_bloque} - {self.id_empleado.nombre_largo} ({self.tipo_evaluador})"

class ClasificacionPorPuesto(models.Model):
    id_puesto = models.ForeignKey(Puesto, on_delete=models.CASCADE, verbose_name="Puesto")
    id_clasificacion = models.ForeignKey(CompetenciaClasificacion, on_delete=models.CASCADE, verbose_name="Clasificación Asignada")

    class Meta:
        verbose_name = "Clasificación por Puesto"
        verbose_name_plural = "Matriz: Clasificaciones por Puesto"
        unique_together = ('id_puesto', 'id_clasificacion') # Evita duplicados

# Tabla para asignar Clasificaciones o Competencias extra directas a un Empleado específico
class ClasificacionPorEmpleado(models.Model):
    id_empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, verbose_name="Empleado")
    id_clasificacion = models.ForeignKey(CompetenciaClasificacion, on_delete=models.CASCADE, verbose_name="Clasificación Extra")
    motivo = models.CharField(max_length=255, blank=True, null=True, help_text="Ej: Proyecto especial 2026")
    
    # Guardará el ID de la competencia creada automáticamente (Oculto para el usuario)
    competencia_exclusiva = models.ForeignKey(
        'Competencia', 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True,
        verbose_name="ID Competencia Exclusiva"
    )

    class Meta:
        verbose_name = "Clasificación Especial por Empleado"
        verbose_name_plural = "Excepciones: Clasificaciones por Empleado"
        unique_together = ('id_empleado', 'id_clasificacion')

class EmpleadoCompetenciaAsignada(models.Model):
    """
    Esta tabla guardará de forma única las competencias palomeadas para cada empleado.
    """
    id_empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='competencias_asignadas')
    id_competencia = models.ForeignKey('Competencia', on_delete=models.CASCADE)
    fecha_asignacion = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Competencia Asignada a Empleado"
        verbose_name = "Competencias Asignadas"
        # Evita que palomeen dos veces la misma competencia para el mismo empleado
        unique_together = ('id_empleado', 'id_competencia') 

    def __str__(self):
        return f"{self.id_empleado.nombre_largo} -> {self.id_competencia.nombre}"        