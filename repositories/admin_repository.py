"""Repository de administradores (inicio de sesión con bloqueo por intentos)."""
from database import transaccion
from repositories.base_repository import BaseRepository

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15


class AdminRepository(BaseRepository):

    def obtener_por_usuario(self, usuario):
        return self._consultar_uno(
            "SELECT id, usuario, password_hash, activo, intentos_fallidos, bloqueado_hasta "
            "FROM Administradores WHERE usuario = ?", (usuario,))

    def esta_bloqueado(self, admin):
        """Calculado en SQL para no depender del reloj de la aplicación."""
        bloqueado = self._escalar(
            "SELECT CASE WHEN bloqueado_hasta > SYSDATETIME() THEN 1 ELSE 0 END "
            "FROM Administradores WHERE id = ?", (admin["id"],))
        return bool(bloqueado)

    def registrar_fallo(self, admin_id):
        with transaccion() as con:
            con.cursor().execute(
                "UPDATE Administradores SET intentos_fallidos = intentos_fallidos + 1, "
                "bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= ? "
                "THEN DATEADD(MINUTE, ?, SYSDATETIME()) ELSE bloqueado_hasta END "
                "WHERE id = ?", (MAX_INTENTOS, MINUTOS_BLOQUEO, admin_id))

    def registrar_acceso(self, admin_id):
        with transaccion() as con:
            con.cursor().execute(
                "UPDATE Administradores SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
                "ultimo_acceso = SYSDATETIME() WHERE id = ?", (admin_id,))
