"""Repository de colaboradores: único lugar donde viven sus consultas SQL (CRUD).
Todas las consultas usan parámetros (?) para evitar inyección SQL."""
try:
    import pyodbc
except ImportError:
    pyodbc = None

from database import transaccion
from models.colaborador import ESTADOS
from repositories.base_repository import BaseRepository

# Áreas por defecto para Render / modo fallback (cuando no hay conexión SQL Server)
AREAS_FALLBACK = [
    {"id": 1, "nombre": "Apoyo Logístico y Eventos"},
    {"id": 2, "nombre": "Comunicaciones y Redes Sociales"},
    {"id": 3, "nombre": "Diseño Gráfico y Multimedia"},
    {"id": 4, "nombre": "Voluntariado en Campo / Proyectos"},
    {"id": 5, "nombre": "Administración y Gestión"}
]


class CorreoDuplicadoError(Exception):
    """El correo ya tiene una solicitud registrada."""


def _es_duplicado(error):
    # 2627 = violación de UNIQUE constraint, 2601 = índice único duplicado
    texto = str(error)
    return "2627" in texto or "2601" in texto


def _escapar_like(texto):
    for caracter in ("\\", "%", "_", "["):
        texto = texto.replace(caracter, "\\" + caracter)
    return texto


class ColaboradorRepository(BaseRepository):
    """CRUD de Colaboradores y su relación muchos a muchos con las áreas."""

    # ---------- Áreas (catálogo) ----------
    def obtener_areas_activas(self):
        areas = self._consultar(
            "SELECT id, nombre FROM AreasColaboracion WHERE activa = 1 ORDER BY id"
        )
        if not areas:
            return AREAS_FALLBACK
        return areas

    # ---------- CREATE ----------
    def guardar(self, colaborador):
        """Guarda el colaborador y sus áreas en una sola transacción."""
        with transaccion() as con:
            if con is None:
                return 1
            cur = con.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO Colaboradores 
                        (nombre_completo, pais, correo, telefono, modalidad, 
                         disponibilidad, motivacion, acepta_privacidad)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        colaborador.nombre,
                        colaborador.pais,
                        colaborador.correo,
                        colaborador.telefono or None,
                        colaborador.modalidad,
                        colaborador.disponibilidad,
                        colaborador.motivacion or None,
                        1,
                    ),
                )
                nuevo_id = cur.fetchone()[0]
                self._guardar_areas(cur, nuevo_id, colaborador.areas)
            except pyodbc.IntegrityError as error:
                if _es_duplicado(error):
                    raise CorreoDuplicadoError() from error
                raise
            return nuevo_id

    @staticmethod
    def _guardar_areas(cursor, colaborador_id, areas):
        for area_id in areas:
            cursor.execute(
                "INSERT INTO ColaboradorAreas (colaborador_id, area_id) VALUES (?, ?)",
                (colaborador_id, area_id),
            )

    # ---------- READ ----------
    def _filtros(self, busqueda, pais, area_id, estado):
        donde, params = ["1 = 1"], []
        if busqueda:
            patron = f"%{_escapar_like(busqueda)}%"
            donde.append("(c.nombre_completo LIKE ? ESCAPE '\\' OR c.correo LIKE ? ESCAPE '\\')")
            params += [patron, patron]
        if pais:
            donde.append("c.pais = ?")
            params.append(pais)
        if area_id:
            donde.append("EXISTS (SELECT 1 FROM ColaboradorAreas ca WHERE ca.colaborador_id = c.id AND ca.area_id = ?)")
            params.append(area_id)
        if estado in ESTADOS:
            donde.append("c.estado = ?")
            params.append(estado)
        return " AND ".join(donde), params

    _SELECT = """
        SELECT c.id, c.nombre_completo, c.pais, c.correo, c.telefono, c.modalidad,
               c.disponibilidad, c.estado, c.fecha_registro,
               (SELECT STRING_AGG(a.nombre, ', ') 
                FROM ColaboradorAreas ca 
                JOIN AreasColaboracion a ON a.id = ca.area_id 
                WHERE ca.colaborador_id = c.id) AS areas
        FROM Colaboradores c
    """

    def listar(self, busqueda="", pais="", area_id=None, estado="", pagina=1, por_pagina=15):
        """Devuelve (filas de la página, total de filas que cumplen el filtro)."""
        donde, params = self._filtros(busqueda, pais, area_id, estado)
        total = self._escalar(f"SELECT COUNT(*) FROM Colaboradores c WHERE {donde}", params)
        filas = self._consultar(
            f"{self._SELECT} WHERE {donde} "
            "ORDER BY c.fecha_registro DESC, c.id DESC "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            params + [(pagina - 1) * por_pagina, por_pagina],
        )
        return filas, total

    def listar_todos(self, busqueda="", pais="", area_id=None, estado=""):
        """Sin paginar: usado para exportar a Excel."""
        donde, params = self._filtros(busqueda, pais, area_id, estado)
        return self._consultar(
            f"{self._SELECT} WHERE {donde} ORDER BY c.fecha_registro DESC", params
        )

    def obtener(self, colaborador_id):
        """Un colaborador con sus áreas: 'areas' (nombres) y 'areas_ids' (para editar)."""
        colaborador = self._consultar_uno(
            "SELECT id, nombre_completo, pais, correo, telefono, modalidad, "
            "disponibilidad, motivacion, estado, fecha_registro "
            "FROM Colaboradores WHERE id = ?", (colaborador_id,)
        )
        if colaborador is None:
            return None
        areas = self._consultar(
            "SELECT a.id, a.nombre FROM ColaboradorAreas ca "
            "JOIN AreasColaboracion a ON a.id = ca.area_id "
            "WHERE ca.colaborador_id = ? ORDER BY a.id", (colaborador_id,)
        )
        colaborador["areas"] = [a["nombre"] for a in areas]
        colaborador["areas_ids"] = [a["id"] for a in areas]
        return colaborador

    # ---------- UPDATE ----------
    def actualizar(self, colaborador_id, colaborador):
        """Actualiza los datos y reemplaza las áreas en una sola transacción.
        Devuelve False si el colaborador no existe."""
        with transaccion() as con:
            if con is None:
                return True
            cur = con.cursor()
            try:
                cur.execute(
                    """
                    UPDATE Colaboradores
                    SET nombre_completo = ?, pais = ?, correo = ?, telefono = ?,
                        modalidad = ?, disponibilidad = ?, motivacion = ?
                    WHERE id = ?
                    """,
                    (
                        colaborador.nombre,
                        colaborador.pais,
                        colaborador.correo,
                        colaborador.telefono or None,
                        colaborador.modalidad,
                        colaborador.disponibilidad,
                        colaborador.motivacion or None,
                        colaborador_id,
                    ),
                )
                if cur.rowcount == 0:
                    return False

                cur.execute("DELETE FROM ColaboradorAreas WHERE colaborador_id = ?", (colaborador_id,))
                self._guardar_areas(cur, colaborador_id, colaborador.areas)
            except pyodbc.IntegrityError as error:
                if _es_duplicado(error):
                    raise CorreoDuplicadoError() from error
                raise
            return True

    def cambiar_estado(self, colaborador_id, estado):
        if estado not in ESTADOS:
            raise ValueError("Estado no válido")
        with transaccion() as con:
            if con is None:
                return True
            cur = con.cursor()
            cur.execute("UPDATE Colaboradores SET estado = ? WHERE id = ?", (estado, colaborador_id))
            return cur.rowcount > 0

    # ---------- DELETE ----------
    def eliminar(self, colaborador_id):
        """Elimina al colaborador; sus filas en ColaboradorAreas se borran en cascada (FK).
        Devuelve False si no existía."""
        with transaccion() as con:
            if con is None:
                return True
            cur = con.cursor()
            cur.execute("DELETE FROM Colaboradores WHERE id = ?", (colaborador_id,))
            return cur.rowcount > 0

    # ---------- Estadísticas del panel ----------
    def estadisticas(self):
        por_estado = {e: 0 for e in ESTADOS}
        for fila in self._consultar(
            "SELECT estado, COUNT(*) AS total FROM Colaboradores GROUP BY estado"
        ):
            por_estado[fila["estado"]] = fila["total"]
        por_pais = [(f["pais"], f["total"]) for f in self._consultar(
            "SELECT TOP 5 pais, COUNT(*) AS total FROM Colaboradores "
            "GROUP BY pais ORDER BY total DESC, pais"
        )]
        por_area = [(f["nombre"], f["total"]) for f in self._consultar(
            "SELECT a.nombre, COUNT(ca.id) AS total FROM AreasColaboracion a "
            "LEFT JOIN ColaboradorAreas ca ON ca.area_id = a.id "
            "GROUP BY a.id, a.nombre ORDER BY total DESC, a.id"
        )]
        ultimos_7 = self._escalar(
            "SELECT COUNT(*) FROM Colaboradores "
            "WHERE fecha_registro >= DATEADD(DAY, -7, SYSDATETIME())"
        ) or 0
        return {
            "total": sum(por_estado.values()),
            "por_estado": por_estado,
            "por_pais": por_pais,
            "por_area": por_area,
            "ultimos_7": ultimos_7,
        }

    def paises_registrados(self):
        return [f["pais"] for f in self._consultar(
            "SELECT DISTINCT pais FROM Colaboradores ORDER BY pais"
        )]