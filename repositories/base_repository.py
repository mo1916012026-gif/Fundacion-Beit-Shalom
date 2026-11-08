"""Clase base de los repositorios (herencia).

Concentra el acceso a la conexión y la lectura de resultados para que los
repositorios hijos solo escriban su SQL y no repitan el manejo de la conexión.
"""
from database import filas_a_diccionarios, obtener_conexion


class BaseRepository:
    """Ofrece consultas de solo lectura; las escrituras usan database.transaccion()."""

    def _consultar(self, sql, params=()):
        """Ejecuta un SELECT y devuelve una lista de diccionarios."""
        con = obtener_conexion()
        try:
            cursor = con.cursor()
            cursor.execute(sql, params)
            return filas_a_diccionarios(cursor)
        finally:
            con.close()

    def _consultar_uno(self, sql, params=()):
        """Devuelve la primera fila como diccionario, o None si no hay resultados."""
        filas = self._consultar(sql, params)
        return filas[0] if filas else None

    def _escalar(self, sql, params=()):
        """Devuelve el primer valor de la primera fila (por ejemplo, un COUNT)."""
        con = obtener_conexion()
        try:
            cursor = con.cursor()
            cursor.execute(sql, params)
            fila = cursor.fetchone()
            return fila[0] if fila else None
        finally:
            con.close()
