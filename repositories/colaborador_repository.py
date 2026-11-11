"""Repositorio para la gestión de colaboradores (funciona con SQL Server local y PostgreSQL en Render)."""
import logging
from database import IS_POSTGRES, transaccion
from models.colaborador import Colaborador

logger = logging.getLogger(__name__)


class CorreoDuplicadoError(Exception):
    """Excepción cuando el correo ya existe en la base de datos."""
    pass


def _adaptar(sql):
    """PostgreSQL usa %s como marcador y SQL Server usa ?. Aquí se escribe con %s y se convierte."""
    if IS_POSTGRES:
        return sql
    return sql.replace("%s", "?")


def _fila_a_dict(fila, columnas):
    """Convierte una fila (tupla o dict) en diccionario con claves en minúscula."""
    if isinstance(fila, dict):
        return {str(k).lower(): v for k, v in fila.items()}
    return {columnas[i].lower(): fila[i] for i in range(min(len(columnas), len(fila)))}


def _primer_valor(fila, clave=None):
    """Lee el primer valor de una fila, sea tupla o diccionario."""
    if fila is None:
        return None
    if isinstance(fila, dict):
        if clave is not None and clave in fila:
            return fila[clave]
        return next(iter(fila.values()), None)
    return fila[0]


class ColaboradorRepository:

    def _consultar(self, sql, parametros=None):
        """Ejecuta SELECT y devuelve una lista de diccionarios."""
        if parametros is None:
            parametros = ()
        try:
            with transaccion() as con:
                if con is None:
                    return []
                cur = con.cursor()
                sql = _adaptar(sql)
                if parametros:
                    cur.execute(sql, parametros)
                else:
                    cur.execute(sql)
                if cur.description is None:
                    return []
                columnas = [d[0] for d in cur.description]
                filas = cur.fetchall()
                return [_fila_a_dict(f, columnas) for f in filas]
        except Exception:
            logger.exception("Error en consulta SQL")
            return []

    def _ejecutar(self, sql, parametros=None):
        """Ejecuta INSERT/UPDATE/DELETE de forma segura."""
        if parametros is None:
            parametros = ()
        try:
            with transaccion() as con:
                if con is None:
                    return False
                cur = con.cursor()
                sql = _adaptar(sql)
                if parametros:
                    cur.execute(sql, parametros)
                else:
                    cur.execute(sql)
                return True
        except Exception:
            logger.exception("Error al ejecutar SQL")
            return False

    def estadisticas(self):
        """Retorna estadísticas sin romper la vista del dashboard."""
        try:
            total = self._consultar("SELECT COUNT(*) AS total FROM Colaboradores")
            tot = total[0].get("total", 0) if total else 0

            por_estado = {}
            for f in self._consultar("SELECT estado, COUNT(*) AS n FROM Colaboradores GROUP BY estado"):
                por_estado[str(f.get("estado") or "").lower()] = f.get("n", 0)

            if IS_POSTGRES:
                sql_7 = "SELECT COUNT(*) AS n FROM Colaboradores WHERE fecha_registro >= NOW() - INTERVAL '7 days'"
            else:
                sql_7 = "SELECT COUNT(*) AS n FROM Colaboradores WHERE fecha_registro >= DATEADD(DAY, -7, SYSDATETIME())"
            ult = self._consultar(sql_7)
            ultimos_7 = ult[0].get("n", 0) if ult else 0

            areas = self._consultar(
                "SELECT a.nombre AS nombre, COUNT(*) AS n "
                "FROM ColaboradorAreas ca JOIN AreasColaboracion a ON a.id = ca.area_id "
                "GROUP BY a.nombre ORDER BY n DESC"
            )
            paises = self._consultar(
                "SELECT pais, COUNT(*) AS n FROM Colaboradores GROUP BY pais ORDER BY n DESC"
            )

            return {
                "total": tot,
                "ultimos_7_dias": ultimos_7,
                "pendiente": por_estado.get("pendiente", 0),
                "en_revision": por_estado.get("en revisión", 0),
                "aprobado": por_estado.get("aprobado", 0),
                "rechazado": por_estado.get("rechazado", 0),
                "areas_populares": [(f["nombre"], f["n"]) for f in areas[:5]],
                "paises_populares": [(f["pais"], f["n"]) for f in paises[:5]],
            }
        except Exception:
            logger.exception("Error al obtener estadísticas")
            return {
                "total": 0, "ultimos_7_dias": 0, "pendiente": 0,
                "en_revision": 0, "aprobado": 0, "rechazado": 0,
                "areas_populares": [], "paises_populares": []
            }

    def paises_registrados(self):
        filas = self._consultar("SELECT DISTINCT pais FROM Colaboradores ORDER BY pais")
        return [f["pais"] for f in filas if "pais" in f and f["pais"]]

    def obtener_areas_activas(self):
        return self._consultar(
            "SELECT id, nombre FROM AreasColaboracion WHERE activa = 1 ORDER BY nombre"
        )

    def listar(self, pagina=1, por_pagina=15, busqueda="", pais="", area_id=None, estado=""):
        sql = (
            "SELECT c.*, (SELECT STRING_AGG(a.nombre, ', ') "
            "FROM ColaboradorAreas ca JOIN AreasColaboracion a ON a.id = ca.area_id "
            "WHERE ca.colaborador_id = c.id) AS areas "
            "FROM Colaboradores c WHERE 1=1"
        )
        params = []
        if busqueda:
            sql += " AND (LOWER(nombre_completo) LIKE %s OR LOWER(correo) LIKE %s)"
            val = f"%{busqueda.lower()}%"
            params.extend([val, val])
        if pais:
            sql += " AND pais = %s"
            params.append(pais)
        if estado:
            sql += " AND LOWER(estado) = %s"
            params.append(estado.lower())
        if area_id:
            sql += (" AND EXISTS (SELECT 1 FROM ColaboradorAreas x "
                    "WHERE x.colaborador_id = c.id AND x.area_id = %s)")
            params.append(area_id)

        filas = self._consultar(sql, tuple(params) if params else None)
        total = len(filas)
        inicio = (pagina - 1) * por_pagina
        fin = inicio + por_pagina
        return filas[inicio:fin], total

    def listar_todos(self, busqueda="", pais="", area_id=None, estado=""):
        filas, _ = self.listar(pagina=1, por_pagina=10000, busqueda=busqueda,
                               pais=pais, area_id=area_id, estado=estado)
        return filas

    def obtener(self, colaborador_id):
        filas = self._consultar("SELECT * FROM Colaboradores WHERE id = %s", (colaborador_id,))
        if not filas:
            return None
        colaborador = filas[0]
        areas = self._consultar(
            "SELECT area_id FROM ColaboradorAreas WHERE colaborador_id = %s", (colaborador_id,)
        )
        colaborador["areas_ids"] = [a["area_id"] for a in areas]
        return colaborador

    def cambiar_estado(self, colaborador_id, nuevo_estado):
        return self._ejecutar(
            "UPDATE Colaboradores SET estado = %s WHERE id = %s", (nuevo_estado, colaborador_id)
        )

    def actualizar(self, colaborador_id, colaborador):
        """Actualiza todos los datos de un colaborador. Devuelve False si no existe."""
        with transaccion() as con:
            if con is None:
                return False
            cur = con.cursor()
            cur.execute(
                _adaptar("SELECT id FROM Colaboradores WHERE LOWER(correo) = %s AND id <> %s"),
                (colaborador.correo.lower(), colaborador_id),
            )
            if cur.fetchone():
                raise CorreoDuplicadoError("El correo ya existe")

            cur.execute(
                _adaptar(
                    """
                    UPDATE Colaboradores
                    SET nombre_completo = %s, pais = %s, correo = %s, telefono = %s,
                        modalidad = %s, disponibilidad = %s, motivacion = %s
                    WHERE id = %s
                    """
                ),
                (
                    colaborador.nombre,
                    colaborador.pais,
                    colaborador.correo,
                    colaborador.telefono,
                    colaborador.modalidad,
                    colaborador.disponibilidad,
                    colaborador.motivacion,
                    colaborador_id,
                ),
            )
            if cur.rowcount == 0:
                return False

            cur.execute(
                _adaptar("DELETE FROM ColaboradorAreas WHERE colaborador_id = %s"),
                (colaborador_id,),
            )
            for area_id in colaborador.areas:
                cur.execute(
                    _adaptar("INSERT INTO ColaboradorAreas (colaborador_id, area_id) VALUES (%s, %s)"),
                    (colaborador_id, area_id),
                )
            return True

    def guardar(self, colaborador):
        with transaccion() as con:
            if con is None:
                return None
            cur = con.cursor()
            cur.execute(
                _adaptar("SELECT id FROM Colaboradores WHERE LOWER(correo) = %s"),
                (colaborador.correo.lower(),),
            )
            if cur.fetchone():
                raise CorreoDuplicadoError("El correo ya existe")

            if IS_POSTGRES:
                insertar = (
                    "INSERT INTO Colaboradores "
                    "(nombre_completo, pais, correo, telefono, modalidad, disponibilidad, "
                    "motivacion, acepta_privacidad, estado) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
                )
            else:
                insertar = (
                    "INSERT INTO Colaboradores "
                    "(nombre_completo, pais, correo, telefono, modalidad, disponibilidad, "
                    "motivacion, acepta_privacidad, estado) "
                    "OUTPUT INSERTED.id "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )

            cur.execute(
                _adaptar(insertar),
                (
                    colaborador.nombre,
                    colaborador.pais,
                    colaborador.correo,
                    colaborador.telefono,
                    colaborador.modalidad,
                    colaborador.disponibilidad,
                    colaborador.motivacion,
                    1 if colaborador.acepta_privacidad else 0,
                    getattr(colaborador, "estado", None) or "Pendiente",
                ),
            )
            nuevo_id = _primer_valor(cur.fetchone(), "id")

            if nuevo_id and colaborador.areas:
                for area_id in colaborador.areas:
                    cur.execute(
                        _adaptar("INSERT INTO ColaboradorAreas (colaborador_id, area_id) VALUES (%s, %s)"),
                        (nuevo_id, area_id),
                    )
            return nuevo_id

    def eliminar(self, colaborador_id):
        return self._ejecutar("DELETE FROM Colaboradores WHERE id = %s", (colaborador_id,))