"""Clase base para todos los repositorios."""
import sys
from pathlib import Path

# Permitir la importación de fakes desde la raíz del proyecto
sys.path.append(str(Path(__file__).resolve().parent.parent))
try:
    import fakes
except ImportError:
    fakes = None

from database import transaccion, filas_a_diccionarios


class BaseRepository:
    """Clase base para todos los repositorios con soporte de fallback para Render."""

    def _consultar(self, query, params=None):
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
        with transaccion() as con:
            if con is None:
                return 0
            cur = con.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            res = cur.fetchone()
            return res[0] if res else 0

    def _ejecutar(self, query, params=None):
        with transaccion() as con:
            if con is None:
                return 0
            cur = con.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            return cur.rowcount