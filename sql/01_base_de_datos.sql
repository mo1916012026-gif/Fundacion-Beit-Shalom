/* =====================================================================
   Fundación Beit Shalom - Base de datos del registro de colaboradores
   Ejecutar en SSMS con un usuario administrador (por ejemplo sa).
   Requiere SQL Server 2017 o superior (se usa STRING_AGG).
   Las reglas de validación están también aquí (CHECK, UNIQUE, FK) para que
   los datos sean correctos aunque alguien se salte la aplicación.
   ===================================================================== */
IF DB_ID('BeitShalomDB') IS NULL
    CREATE DATABASE BeitShalomDB;
GO
USE BeitShalomDB;
GO

/* ---------- Colaboradores ---------- */
CREATE TABLE Colaboradores (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    nombre_completo   NVARCHAR(150) NOT NULL,
    pais              NVARCHAR(80)  NOT NULL,
    correo            NVARCHAR(150) NOT NULL,
    telefono          NVARCHAR(30)  NULL,
    modalidad         NVARCHAR(30)  NOT NULL,
    disponibilidad    NVARCHAR(100) NOT NULL,
    motivacion        NVARCHAR(1000) NULL,
    acepta_privacidad BIT NOT NULL,
    fecha_registro    DATETIME2 NOT NULL CONSTRAINT DF_Colab_Fecha DEFAULT SYSDATETIME(),
    estado            NVARCHAR(20) NOT NULL CONSTRAINT DF_Colab_Estado DEFAULT 'Pendiente',

    CONSTRAINT UQ_Colaboradores_Correo UNIQUE (correo),

    CONSTRAINT CK_Colab_Nombre
        CHECK (LEN(LTRIM(RTRIM(nombre_completo))) >= 5),
    CONSTRAINT CK_Colab_Pais
        CHECK (LEN(LTRIM(RTRIM(pais))) >= 2),
    CONSTRAINT CK_Colab_Correo
        CHECK (correo LIKE '%_@_%._%' AND correo NOT LIKE '% %'),
    CONSTRAINT CK_Colab_Telefono
        CHECK (telefono IS NULL
               OR (LEN(telefono) >= 7 AND telefono NOT LIKE '%[^0-9+() -]%')),
    CONSTRAINT CK_Colab_Modalidad
        CHECK (modalidad IN ('Presencial', 'Virtual', 'Ambas')),
    CONSTRAINT CK_Colab_Disponibilidad
        CHECK (disponibilidad IN ('Entre semana', 'Fines de semana',
                                  'Horarios flexibles', 'Ocasional')),
    CONSTRAINT CK_Colab_Estado
        CHECK (estado IN ('Pendiente', 'En revisión', 'Aprobado', 'Rechazado')),
    CONSTRAINT CK_Colab_Privacidad
        CHECK (acepta_privacidad = 1)
);
GO
CREATE INDEX IX_Colab_Estado ON Colaboradores (estado, fecha_registro DESC);
CREATE INDEX IX_Colab_Pais   ON Colaboradores (pais);
GO

/* ---------- Áreas de colaboración ---------- */
CREATE TABLE AreasColaboracion (
    id     INT IDENTITY(1,1) PRIMARY KEY,
    nombre NVARCHAR(100) NOT NULL UNIQUE,
    activa BIT NOT NULL CONSTRAINT DF_Areas_Activa DEFAULT 1
);
GO
INSERT INTO AreasColaboracion (nombre) VALUES
 (N'Voluntariado presencial'),
 (N'Apoyo profesional o técnico'),
 (N'Apoyo educativo'),
 (N'Organización de actividades'),
 (N'Comunicación y difusión'),
 (N'Apoyo administrativo'),
 (N'Donaciones y gestión de recursos'),
 (N'Otro tipo de colaboración');
GO

/* ---------- Relación muchos a muchos ---------- */
CREATE TABLE ColaboradorAreas (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    colaborador_id INT NOT NULL,
    area_id        INT NOT NULL,
    CONSTRAINT FK_CA_Colaborador FOREIGN KEY (colaborador_id)
        REFERENCES Colaboradores(id) ON DELETE CASCADE,
    CONSTRAINT FK_CA_Area FOREIGN KEY (area_id)
        REFERENCES AreasColaboracion(id),
    CONSTRAINT UQ_Colaborador_Area UNIQUE (colaborador_id, area_id)
);
GO

/* ---------- Administradores (contraseña SIEMPRE como hash) ---------- */
CREATE TABLE Administradores (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    usuario           NVARCHAR(50)  NOT NULL UNIQUE,
    password_hash     NVARCHAR(255) NOT NULL,
    activo            BIT NOT NULL CONSTRAINT DF_Admin_Activo DEFAULT 1,
    intentos_fallidos INT NOT NULL CONSTRAINT DF_Admin_Intentos DEFAULT 0,
    bloqueado_hasta   DATETIME2 NULL,
    ultimo_acceso     DATETIME2 NULL,
    fecha_creacion    DATETIME2 NOT NULL CONSTRAINT DF_Admin_Fecha DEFAULT SYSDATETIME(),
    CONSTRAINT CK_Admin_Usuario CHECK (LEN(usuario) >= 4)
);
GO
