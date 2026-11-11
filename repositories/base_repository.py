"""Clase base para todos los repositorios."""
from database import IS_POSTGRES, transaccion, filas_a_diccionarios


def _adaptar(query):
    """SQL Server usa '?' como marcador y PostgreSQL usa '%s'. Convierte si hace falta."""
    if IS_POSTGRES:
        return query.replace("?", "%s")
    return query


class BaseRepository:
    """Clase base para todos los repositorios con soporte de fallback para Render."""

    def _consultar(self, query, params=None):
        query = _adaptar(query)
        with transaccion() as con:
            if con is None:
                return []
            cur = con.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            return filas_a_diccionarios(cur)

    def _consultar_uno(self, query, params=None):
        filas = self._consultar(query, params)
        return filas[0] if filas else None

    def _escalar(self, query, params=None):
        query = _adaptar(query)
        with transaccion() as con:
            if con is None:
                return 0
            cur = con.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            res = cur.fetchone()
            if not res:
                return 0
            if isinstance(res, dict):
                return next(iter(res.values()))
            return res[0]

    def _ejecutar(self, query, params=None):
        query = _adaptar(query)
        with transaccion() as con:
            if con is None:
                return 0
            cur = con.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            return cur.rowcount