"""Conexión a SQL Server. Es el único archivo que sabe cómo conectarse."""
from contextlib import contextmanager

import pyodbc

from config import Config


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
    return pyodbc.connect(_cadena_conexion(), timeout=Config.DB_TIMEOUT)


@contextmanager
def transaccion():
    """Abre una conexión; confirma si todo sale bien y revierte si hay error."""
    conexion = obtener_conexion()
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def filas_a_diccionarios(cursor):
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
