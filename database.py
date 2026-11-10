"""Conexión a la base de datos: soporta SQL Server (local via pyodbc) y PostgreSQL (Render via psycopg2)."""
import os
from contextlib import contextmanager

from config import Config

# Detectar si estamos en Render con PostgreSQL o en Local con SQL Server
IS_POSTGRES = os.environ.get("DATABASE_URL") is not None

if IS_POSTGRES:
    try:
        import psycopg2  # type: ignore
        from psycopg2.extras import RealDictCursor  # type: ignore
    except ImportError:
        psycopg2 = None
        RealDictCursor = None
    pyodbc = None
else:
    try:
        import pyodbc
    except ImportError:
        pyodbc = None


def _valor(texto):
    """Escapa un valor para la cadena de conexión ODBC (por si lleva ; o })."""
    return "{" + str(texto).replace("}", "}}") + "}"


def _cadena_conexion():
    partes = [
        f"DRIVER={{{Config.DB_DRIVER}}}",
        f"SERVER={Config.DB_SERVER}",
        f"DATABASE={Config.DB_NAME}",
        f"Encrypt={Config.DB_ENCRYPT}",
        f"TrustServerCertificate={Config.DB_TRUST_CERT}",
    ]
    if Config.DB_TRUSTED:
        partes.append("Trusted_Connection=yes")
    else:
        partes.append(f"UID={_valor(Config.DB_USER)}")
        partes.append(f"PWD={_valor(Config.DB_PASSWORD)}")
    return ";".join(partes) + ";"


def obtener_conexion():
    url = os.environ.get("DATABASE_URL")
    if IS_POSTGRES and url:
        # En Render arreglamos el prefijo de la URL de PostgreSQL si es necesario
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, cursor_factory=RealDictCursor)
    
    if pyodbc is None:
        return None
    return pyodbc.connect(_cadena_conexion(), timeout=Config.DB_TIMEOUT)


@contextmanager
def transaccion():
    """Abre una conexión y gestiona transacciones para PostgreSQL o SQL Server."""
    conexion = obtener_conexion()
    if conexion is None:
        yield None
        return

    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def filas_a_diccionarios(cursor):
    if cursor is None:
        return []
    if IS_POSTGRES:
        # En psycopg2 con RealDictCursor las filas ya son dicts
        return [dict(f) for f in cursor.fetchall()]
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def inicializar_db():
    """Crea automáticamente las tablas en PostgreSQL (Render) o SQL Server (Local)."""
    with transaccion() as con:
        if con is None:
            return
        cur = con.cursor()
        if IS_POSTGRES:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Colaboradores (
                    id SERIAL PRIMARY KEY,
                    nombre_completo VARCHAR(255) NOT NULL,
                    pais VARCHAR(100) NOT NULL,
                    correo VARCHAR(255) UNIQUE NOT NULL,
                    telefono VARCHAR(50),
                    modalidad VARCHAR(100),
                    disponibilidad VARCHAR(100),
                    motivacion TEXT,
                    acepta_privacidad INT DEFAULT 1,
                    estado VARCHAR(50) DEFAULT 'Pendiente',
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS AreasColaboracion (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    activa INT DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS ColaboradorAreas (
                    id SERIAL PRIMARY KEY,
                    colaborador_id INT REFERENCES Colaboradores(id) ON DELETE CASCADE,
                    area_id INT REFERENCES AreasColaboracion(id) ON DELETE CASCADE
                );
            """)