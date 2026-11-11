"""Revisa, sin SQL Server, que cada consulta de los repositorios tenga tantos parámetros
como signos '?' (un descuido típico) y que el CRUD use las sentencias esperadas.
Uso:  python tests/test_repositorios.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.update(SECRET_KEY="x" * 32)

import fakes  # noqa: E402  (prepara pyodbc falso si hace falta)
import database  # noqa: E402
import repositories.base_repository as base  # noqa: E402
from models.colaborador import Colaborador  # noqa: E402
from repositories.admin_repository import AdminRepository  # noqa: E402
from repositories.colaborador_repository import ColaboradorRepository  # noqa: E402

EJECUTADAS = []


class CursorFalso:
    description = None
    rowcount = 1

    def __init__(self):
        self._filas = []

    def execute(self, sql, params=()):
        params = list(params)
        assert sql.count("?") == len(params), f"Parámetros incorrectos en: {sql!r} -> {params}"
        EJECUTADAS.append(" ".join(sql.split()))
        columnas, filas = [("id", "nombre")], [(1, "x")]
        if "GROUP BY estado" in sql:
            columnas, filas = [("estado", "total")], [("Pendiente", 2)]
        elif "TOP 5 pais" in sql:
            columnas, filas = [("pais", "total")], [("El Salvador", 2)]
        elif "LEFT JOIN" in sql:
            columnas, filas = [("nombre", "total")], [("Area 1", 2)]
        elif "DISTINCT pais" in sql:
            columnas, filas = [("pais",)], [("El Salvador",)]
        elif "COUNT(*)" in sql:
            columnas, filas = [("total",)], [(3,)]
        if "SELECT area_id FROM ColaboradorAreas" in sql:
            columnas, filas = [("area_id",)], [(1,)]
        if "WHERE LOWER(correo)" in sql and sql.lstrip().startswith("SELECT id FROM Colaboradores"):
            filas = []  # el correo aún no existe
        self.description = [(c,) for c in columnas[0]]
        self._filas = filas

    def fetchall(self):
        return self._filas

    def fetchone(self):
        return self._filas[0] if self._filas else None


class ConexionFalsa:
    def cursor(self):
        return CursorFalso()

    def commit(self):
        EJECUTADAS.append("COMMIT")

    def rollback(self):
        EJECUTADAS.append("ROLLBACK")

    def close(self):
        pass


database.obtener_conexion = ConexionFalsa
base.obtener_conexion = ConexionFalsa


def colaborador():
    return Colaborador("Ana Pérez", "El Salvador", "a@b.co", "", "Virtual", "Ocasional", "", ["1", "2"], True)


def run():
    repo, admin = ColaboradorRepository(), AdminRepository()
    assert issubclass(ColaboradorRepository, base.BaseRepository)
    assert issubclass(AdminRepository, base.BaseRepository)

    repo.obtener_areas_activas()
    assert repo.guardar(colaborador()) == 1
    assert sum(s.startswith("INSERT INTO ColaboradorAreas") for s in EJECUTADAS) == 2
    repo.listar(busqueda="ana", pais="El Salvador", area_id=2, estado="Pendiente", pagina=2)
    repo.listar_todos(busqueda="ana")
    persona = repo.obtener(1)
    assert persona["areas_ids"] == [1]
    EJECUTADAS.clear()
    assert repo.actualizar(1, colaborador()) is True
    assert EJECUTADAS[0].startswith("UPDATE Colaboradores SET nombre_completo")
    assert any(s.startswith("DELETE FROM ColaboradorAreas") for s in EJECUTADAS)
    assert sum(s.startswith("INSERT INTO ColaboradorAreas") for s in EJECUTADAS) == 2
    assert EJECUTADAS[-1] == "COMMIT"
    EJECUTADAS.clear()
    assert repo.eliminar(1) is True
    assert EJECUTADAS[0] == "DELETE FROM Colaboradores WHERE id = ?"
    assert repo.cambiar_estado(1, "Aprobado") is True
    try:
        repo.cambiar_estado(1, "Hackeado")
        raise AssertionError("debía rechazar un estado inválido")
    except ValueError:
        pass
    datos = repo.estadisticas()
    assert datos["total"] == 2 and datos["ultimos_7"] == 3 and datos["por_pais"][0][0] == "El Salvador"
    assert repo.paises_registrados() == ["El Salvador"]
    assert admin.obtener_por_usuario("admin")["id"] == 1
    assert admin.esta_bloqueado({"id": 1}) is True
    admin.registrar_fallo(1)
    admin.registrar_acceso(1)
    print("REPOSITORIOS OK:", len(EJECUTADAS), "sentencias revisadas en esta tanda")


run()
