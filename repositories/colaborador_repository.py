import os
from database import transaccion
from models.colaborador import ESTADOS
from repositories.base_repository import BaseRepository

try:
    import pyodbc
except ImportError:
    pyodbc = None

IS_POSTGRES = os.environ.get("DATABASE_URL") is not None
PH = "%s" if IS_POSTGRES else "?"

AREAS_FALLBACK = [
    {"id": 1, "nombre": "Voluntariado presencial"},
    {"id": 2, "nombre": "Apoyo profesional o técnico"},
    {"id": 3, "nombre": "Apoyo educativo"},
    {"id": 4, "nombre": "Organización de actividades"},
    {"id": 5, "nombre": "Comunicación y difusión"},
    {"id": 6, "nombre": "Apoyo administrativo"},
    {"id": 7, "nombre": "Donaciones y gestión de recursos"},
    {"id": 8, "nombre": "Otro tipo de colaboración"}
]

class CorreoDuplicadoError(Exception):
    """El correo ya tiene una solicitud registrada."""
    pass

def _es_duplicado(error):
    texto = str(error)
    return "2627" in texto or "2601" in texto or "unique" in texto.lower()

def _escapar_like(texto):
    for caracter in ("\\", "%", "_", "["):
        texto = texto.replace(caracter, "\\" + caracter)
    return texto

class ColaboradorRepository(BaseRepository):

    def obtener_areas_activas(self):
        areas = self._consultar(
            "SELECT id, nombre FROM AreasColaboracion WHERE activa = 1 ORDER BY id"
        )
        if not areas:
            return AREAS_FALLBACK
        return areas

    def guardar(self, colaborador):
        with transaccion() as con:
            if con is None:
                return 1
            cur = con.cursor()
            try:
                if IS_POSTGRES:
                    query = """
                        INSERT INTO Colaboradores
                        (nombre_completo, pais, correo, telefono, modalidad, disponibilidad, motivacion, acepta_privacidad)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """
                else:
                    query = """
                        INSERT INTO Colaboradores
                        (nombre_completo, pais, correo, telefono, modalidad, disponibilidad, motivacion, acepta_privacidad)
                        OUTPUT INSERTED.id
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """

                cur.execute(query, (
                    colaborador.nombre,
                    colaborador.pais,
                    colaborador.correo,
                    colaborador.telefono or None,
                    colaborador.modalidad,
                    colaborador.disponibilidad,
                    colaborador.motivacion or None,
                    1
                ))
                nuevo_id = cur.fetchone()[0]
                self._guardar_areas(cur, nuevo_id, colaborador.areas)
            except Exception as error:
                if _es_duplicado(error):
                    raise CorreoDuplicadoError() from error
                raise
            return nuevo_id

    @staticmethod
    def _guardar_areas(cursor, colaborador_id, areas):
        query = f"INSERT INTO ColaboradorAreas (colaborador_id, area_id) VALUES ({PH}, {PH})"
        for area_id in areas:
            cursor.execute(query, (colaborador_id, area_id))

    def _filtros(self, busqueda, pais, area_id, estado):
        donde, params = ["1 = 1"], []
        if busqueda:
            patron = f"%{_escapar_like(busqueda)}%"
            donde.append(f"(c.nombre_completo LIKE {PH} ESCAPE '\\' OR c.correo LIKE {PH} ESCAPE '\\')")
            params += [patron, patron]
        if pais:
            donde.append(f"c.pais = {PH}")
            params.append(pais)
        if area_id:
            donde.append(f"EXISTS (SELECT 1 FROM ColaboradorAreas ca WHERE ca.colaborador_id = c.id AND ca.area_id = {PH})")
            params.append(area_id)
        if estado in ESTADOS:
            donde.append(f"c.estado = {PH}")
            params.append(estado)
        return " AND ".join(donde), params

    @property
    def _SELECT(self):
        return f"""
            SELECT c.id, c.nombre_completo, c.pais, c.correo, c.telefono, c.modalidad,
                   c.disponibilidad, c.estado, c.fecha_registro,
                   (SELECT STRING_AGG(a.nombre, ', ')
                    FROM ColaboradorAreas ca
                    JOIN AreasColaboracion a ON a.id = ca.area_id
                    WHERE ca.colaborador_id = c.id) AS areas
            FROM Colaboradores c
        """

    def listar(self, busqueda="", pais="", area_id=None, estado="", pagina=1, por_pagina=15):
        donde, params = self._filtros(busqueda, pais, area_id, estado)
        total = self._escalar(f"SELECT COUNT(*) FROM Colaboradores c WHERE {donde}", params)
        
        offset = (pagina - 1) * por_pagina
        if IS_POSTGRES:
            query = f"{self._SELECT} WHERE {donde} ORDER BY c.fecha_registro DESC LIMIT {PH} OFFSET {PH}"
            params_paginacion = params + [por_pagina, offset]
        else:
            query = f"{self._SELECT} WHERE {donde} ORDER BY c.fecha_registro DESC OFFSET {PH} ROWS FETCH NEXT {PH} ROWS ONLY"
            params_paginacion = params + [offset, por_pagina]

        filas = self._consultar(query, params_paginacion)
        return filas, total

    def obtener(self, colaborador_id):
        query = f"""
            SELECT id, nombre_completo, pais, correo, telefono, modalidad,
                   disponibilidad, motivacion, estado, fecha_registro
            FROM Colaboradores WHERE id = {PH}
        """
        colaborador = self._consultar_uno(query, (colaborador_id,))
        if colaborador is None:
            return None
            
        query_areas = f"""
            SELECT a.id, a.nombre FROM ColaboradorAreas ca
            JOIN AreasColaboracion a ON a.id = ca.area_id
            WHERE ca.colaborador_id = {PH} ORDER BY a.id
        """
        areas = self._consultar(query_areas, (colaborador_id,))
        colaborador["areas"] = [a["nombre"] for a in areas]
        colaborador["areas_ids"] = [a["id"] for a in areas]
        return colaborador

    def estadisticas(self):
        por_estado = {e: 0 for e in ESTADOS}
        for fila in self._consultar("SELECT estado, COUNT(*) AS total FROM Colaboradores GROUP BY estado"):
            por_estado[fila["estado"]] = fila["total"]

        por_pais = self._consultar(
            f"SELECT c.pais, COUNT(*) AS total FROM Colaboradores c GROUP BY c.pais ORDER BY total DESC LIMIT 5" if IS_POSTGRES
            else "SELECT TOP 5 c.pais, COUNT(*) AS total FROM Colaboradores c GROUP BY c.pais ORDER BY total DESC"
        )

        por_area = self._consultar("""
            SELECT a.nombre, COUNT(ca.id) AS total FROM AreasColaboracion a
            LEFT JOIN ColaboradorAreas ca ON a.id = ca.area_id
            GROUP BY a.id, a.nombre ORDER BY total DESC, a.id
        """)

        filtro_7dias = "fecha_registro >= NOW() - INTERVAL '7 days'" if IS_POSTGRES else "fecha_registro >= DATEADD(DAY, -7, SYSDATETIME())"
        ultimos_7 = self._escalar(f"SELECT COUNT(*) FROM Colaboradores WHERE {filtro_7dias}") or 0

        return {
            "total": sum(por_estado.values()),
            "por_estado": por_estado,
            "por_pais": por_pais,
            "por_area": por_area,
            "ultimos_7": ultimos_7,
        }

    def paises_registrados(self):
        return [f["pais"] for f in self._consultar("SELECT DISTINCT pais FROM Colaboradores ORDER BY pais")]