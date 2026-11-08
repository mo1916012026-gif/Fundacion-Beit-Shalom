"""Repositorios falsos en memoria (con CRUD completo) para probar sin SQL Server."""
import datetime
import types
import sys

if "pyodbc" not in sys.modules:
    try:
        import pyodbc  # noqa: F401
    except ImportError:
        sys.modules["pyodbc"] = types.SimpleNamespace(
            IntegrityError=type("IntegrityError", (Exception,), {}), connect=None)

from repositories.colaborador_repository import CorreoDuplicadoError
from werkzeug.security import generate_password_hash

AREAS = [{"id": i, "nombre": f"Area {i}"} for i in range(1, 9)]
ESTADOS = ("Pendiente", "En revisión", "Aprobado", "Rechazado")


class FakeColaboradores:
    def __init__(self):
        self.filas = {}
        self.siguiente = 1

    def obtener_areas_activas(self):
        return AREAS

    def _duplicado(self, correo, excepto=None):
        return any(f["correo"] == correo and i != excepto for i, f in self.filas.items())

    def guardar(self, c):
        if self._duplicado(c.correo):
            raise CorreoDuplicadoError()
        nuevo = self.siguiente
        self.siguiente += 1
        self.filas[nuevo] = self._fila(nuevo, c, "Pendiente", datetime.datetime.now())
        return nuevo

    def actualizar(self, i, c):
        if i not in self.filas:
            return False
        if self._duplicado(c.correo, excepto=i):
            raise CorreoDuplicadoError()
        anterior = self.filas[i]
        self.filas[i] = self._fila(i, c, anterior["estado"], anterior["fecha_registro"])
        return True

    def eliminar(self, i):
        return self.filas.pop(i, None) is not None

    @staticmethod
    def _fila(i, c, estado, fecha):
        return {"id": i, "nombre_completo": c.nombre, "pais": c.pais, "correo": c.correo,
                "telefono": c.telefono or None, "modalidad": c.modalidad,
                "disponibilidad": c.disponibilidad, "motivacion": c.motivacion or None,
                "estado": estado, "fecha_registro": fecha, "areas_ids": list(c.areas)}

    def obtener(self, i):
        f = self.filas.get(i)
        if f is None:
            return None
        f = dict(f)
        f["areas"] = [a["nombre"] for a in AREAS if a["id"] in f["areas_ids"]]
        return f

    def listar(self, **k):
        filas = []
        for f in self.filas.values():
            g = dict(f)
            g["areas"] = ", ".join(a["nombre"] for a in AREAS if a["id"] in f["areas_ids"])
            filas.append(g)
        return filas, len(filas)

    def listar_todos(self, **k):
        return self.listar()[0]

    def cambiar_estado(self, i, e):
        if i not in self.filas:
            return False
        self.filas[i]["estado"] = e
        return True

    def paises_registrados(self):
        return sorted({f["pais"] for f in self.filas.values()})

    def estadisticas(self):
        por_estado = {e: 0 for e in ESTADOS}
        for f in self.filas.values():
            por_estado[f["estado"]] += 1
        return {"total": len(self.filas), "por_estado": por_estado,
                "por_pais": [(p, 1) for p in self.paises_registrados()],
                "por_area": [(a["nombre"], 0) for a in AREAS], "ultimos_7": len(self.filas)}


class FakeAdmin:
    h = generate_password_hash("claveSegura123")

    def obtener_por_usuario(self, u):
        return ({"id": 1, "usuario": u, "password_hash": self.h, "activo": True}
                if u == "admin" else None)

    def esta_bloqueado(self, a):
        return False

    def registrar_fallo(self, i):
        pass

    def registrar_acceso(self, i):
        pass
