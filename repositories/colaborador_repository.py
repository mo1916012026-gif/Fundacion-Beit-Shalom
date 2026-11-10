"""Repositorio para la gestión de colaboradores en la base de datos (Compatible con SQL Server y PostgreSQL)."""
import logging
from database import filas_a_diccionarios, transaccion
from models.colaborador import Colaborador

logger = logging.getLogger(__name__)


class CorreoDuplicadoError(Exception):
    """Excepción cuando el correo ya existe en la base de datos."""
    pass


class ColaboradorRepository:

    def _consultar(self, sql, parametros=()):
        """Ejecuta SELECT y convierte llaves a minúsculas para evitar KeyError entre PostgreSQL y SQL Server."""
        try:
            with transaccion() as con:
                if con is None:
                    return []
                cur = con.cursor()
                cur.execute(sql, parametros)
                filas = filas_a_diccionarios(cur)
                return [{k.lower(): v for k, v in f.items()} for f in filas]
        except Exception as e:
            logger.error(f"Error en consulta SQL: {e}")
            return []

    def _ejecutar(self, sql, parametros=()):
        """Ejecuta INSERT, UPDATE o DELETE de forma segura."""
        try:
            with transaccion() as con:
                if con is None:
                    return False
                cur = con.cursor()
                cur.execute(sql, parametros)
                return True
        except Exception as e:
            logger.error(f"Error al ejecutar SQL: {e}")
            return False

    def estadisticas(self):
        """Retorna las estadísticas del dashboard calculadas de forma segura."""
        try:
            total = self._consultar("SELECT COUNT(*) AS total FROM Colaboradores")
            tot = total[0]["total"] if total else 0

            pend = self._consultar("SELECT COUNT(*) AS total FROM Colaboradores WHERE LOWER(estado) = 'pendiente'")
            p_val = pend[0]["total"] if pend else 0

            rev = self._consultar("SELECT COUNT(*) AS total FROM Colaboradores WHERE LOWER(estado) LIKE '%revisi%'")
            r_val = rev[0]["total"] if rev else 0

            aprob = self._consultar("SELECT COUNT(*) AS total FROM Colaboradores WHERE LOWER(estado) = 'aprobado'")
            a_val = aprob[0]["total"] if aprob else 0

            rech = self._consultar("SELECT COUNT(*) AS total FROM Colaboradores WHERE LOWER(estado) = 'rechazado'")
            rec_val = rech[0]["total"] if rech else 0

            return {
                "total": tot,
                "ultimos_7_dias": tot,
                "pendiente": p_val,
                "en_revision": r_val,
                "aprobado": a_val,
                "rechazado": rec_val,
                "areas_populares": [],
                "paises_populares": [],
            }
        except Exception as e:
            logger.error(f"Error al calcular estadísticas: {e}")
            return {
                "total": 0, "ultimos_7_dias": 0, "pendiente": 0,
                "en_revision": 0, "aprobado": 0, "rechazado": 0,
                "areas_populares": [], "paises_populares": []
            }

    def paises_registrados(self):
        filas = self._consultar("SELECT DISTINCT pais FROM Colaboradores ORDER BY pais")
        return [f["pais"] for f in filas if "pais" in f and f["pais"]]

    def obtener_areas_activas(self):
        return self._consultar("SELECT id, nombre FROM AreasColaboracion WHERE activa = 1 ORDER BY nombre")

    def listar(self, pagina=1, por_pagina=15, busqueda="", pais="", area_id=None, estado=""):
        sql = "SELECT * FROM Colaboradores WHERE 1=1"
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

        filas = self._consultar(sql, tuple(params))
        total = len(filas)
        inicio = (pagina - 1) * por_pagina
        fin = inicio + por_pagina
        return filas[inicio:fin], total

    def listar_todos(self, busqueda="", pais="", area_id=None, estado=""):
        filas, _ = self.listar(pagina=1, por_pagina=10000, busqueda=busqueda, pais=pais, area_id=area_id, estado=estado)
        return filas

    def obtener(self, colaborador_id):
        filas = self._consultar("SELECT * FROM Colaboradores WHERE id = %s", (colaborador_id,))
        if not filas:
            return None
        colaborador = filas[0]
        areas = self._consultar("SELECT area_id FROM ColaboradorAreas WHERE colaborador_id = %s", (colaborador_id,))
        colaborador["areas_ids"] = [a["area_id"] for a in areas]
        return colaborador

    def cambiar_estado(self, colaborador_id, nuevo_estado):
        return self._ejecutar("UPDATE Colaboradores SET estado = %s WHERE id = %s", (nuevo_estado, colaborador_id))

    def guardar(self, colaborador):
        with transaccion() as con:
            if con is None:
                return None
            cur = con.cursor()
            cur.execute("SELECT id FROM Colaboradores WHERE LOWER(correo) = %s", (colaborador.correo.lower(),))
            if cur.fetchone():
                raise CorreoDuplicadoError("El correo ya existe")

            cur.execute(
                """
                INSERT INTO Colaboradores 
                (nombre_completo, pais, correo, telefono, modalidad, disponibilidad, motivacion, acepta_privacidad, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    colaborador.nombre_completo,
                    colaborador.pais,
                    colaborador.correo,
                    colaborador.telefono,
                    colaborador.modalidad,
                    colaborador.disponibilidad,
                    colaborador.motivacion,
                    1 if colaborador.acepta_privacidad else 0,
                    colaborador.estado or "Pendiente",
                ),
            )
            res = cur.fetchone()
            nuevo_id = res[0] if res else None

            if nuevo_id and colaborador.areas:
                for area_id in colaborador.areas:
                    cur.execute(
                        "INSERT INTO ColaboradorAreas (colaborador_id, area_id) VALUES (%s, %s)",
                        (nuevo_id, area_id),
                    )
            return nuevo_id

    def eliminar(self, colaborador_id):
        return self._ejecutar("DELETE FROM Colaboradores WHERE id = %s", (colaborador_id,))