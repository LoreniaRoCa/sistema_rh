-- 1. Tabla de Departamentos
CREATE TABLE departamento (
    id_departamento SERIAL PRIMARY KEY,
    descripcion VARCHAR(150) NOT NULL,
    id_jefe INT -- Se asignará después de crear la tabla empleado para evitar errores de jerarquía
);

-- 2. Tabla de Puestos
CREATE TABLE puesto (
    id_puesto SERIAL PRIMARY KEY,
    descripcion VARCHAR(150) NOT NULL
);

-- 3. Tabla de Empleados
CREATE TABLE empleado (
    id_empleado SERIAL PRIMARY KEY,
    nombre_largo VARCHAR(255) NOT NULL,
    id_jefe INT REFERENCES empleado(id_empleado) ON DELETE SET NULL,
    id_departamento INT REFERENCES departamento(id_departamento) ON DELETE SET NULL,
    id_puesto INT REFERENCES puesto(id_puesto) ON DELETE SET NULL
);

-- Ahora que existe empleado, enlazamos formalmente el jefe del departamento
ALTER TABLE departamento 
ADD CONSTRAINT fk_departamento_jefe 
FOREIGN KEY (id_jefe) REFERENCES empleado(id_empleado) ON DELETE SET NULL;

-- 4. Tabla de Clasificación de Competencias
CREATE TABLE competencia_clasificacion (
    id_clasificacion SERIAL PRIMARY KEY,
    descripcion VARCHAR(150) NOT NULL,
    tipo VARCHAR(20) CHECK (tipo IN ('GENERAL', 'ESPECIFICA')),
    id_puesto INT REFERENCES puesto(id_puesto) ON DELETE SET NULL -- NULL si es General
);

-- 5. Tabla de Competencias individuales
CREATE TABLE competencia (
    id_competencia SERIAL PRIMARY KEY,
    id_clasificacion INT NOT NULL REFERENCES competencia_clasificacion(id_clasificacion) ON DELETE CASCADE,
    descripcion TEXT NOT NULL
);

-- 6. Tabla de Periodos de Evaluación
CREATE TABLE evaluacion (
    id_evaluacion VARCHAR(20) PRIMARY KEY, -- Ejemplo: "2026-01"
    descripcion VARCHAR(255) NOT NULL,
    fecha_inicial DATE NOT NULL,
    fecha_final DATE NOT NULL
);

-- 7. Tabla Detalle de Evaluaciones (Calificaciones)
CREATE TABLE evaluacion_det (
    id_evaluacion VARCHAR(20) REFERENCES evaluacion(id_evaluacion) ON DELETE CASCADE,
    id_competencia INT REFERENCES competencia(id_competencia) ON DELETE CASCADE,
    id_empleado INT REFERENCES empleado(id_empleado) ON DELETE CASCADE,
    calificacion INT CHECK (calificacion BETWEEN 1 AND 5),
    tipo CHAR(1) CHECK (tipo IN ('J', 'E')), -- 'J' para Jefe, 'E' para Empleado (Autoevaluación)
    PRIMARY KEY (id_evaluacion, id_competencia, id_empleado, tipo)
);