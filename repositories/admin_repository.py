"""Repository de administradores (inicio de sesión con bloqueo por intentos)."""
import werkzeug.security as security
from database import IS_POSTGRES
from repositories.base_repository import BaseRepository

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15


class AdminRepository(BaseRepository):

    def obtener_por_usuario(self, usuario):
        if not usuario:
            return None
        return self._consultar_uno(
            "SELECT id, usuario, password_hash, activo, intentos_fallidos, bloqueado_hasta "
            "FROM Administradores WHERE LOWER(usuario) = LOWER(?)", (usuario,)
        )

    def esta_bloqueado(self, admin):
        """Calculado en SQL para no depender del reloj de la aplicación."""
        ahora = "NOW()" if IS_POSTGRES else "SYSDATETIME()"
        bloqueado = self._escalar(
            f"SELECT CASE WHEN bloqueado_hasta > {ahora} THEN 1 ELSE 0 END "
            "FROM Administradores WHERE id = ?", (admin["id"],)
        )
        return bool(bloqueado)

    def registrar_fallo(self, admin_id):
        if IS_POSTGRES:
            sql = (
                "UPDATE Administradores SET intentos_fallidos = intentos_fallidos + 1, "
                "bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= ? "
                "THEN NOW() + (? * INTERVAL '1 minute') ELSE bloqueado_hasta END "
                "WHERE id = ?"
            )
        else:
            sql = (
                "UPDATE Administradores SET intentos_fallidos = intentos_fallidos + 1, "
                "bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= ? "
                "THEN DATEADD(MINUTE, ?, SYSDATETIME()) ELSE bloqueado_hasta END "
                "WHERE id = ?"
            )
        self._ejecutar(sql, (MAX_INTENTOS, MINUTOS_BLOQUEO, admin_id))

    def registrar_acceso(self, admin_id):
        ahora = "NOW()" if IS_POSTGRES else "SYSDATETIME()"
        self._ejecutar(
            "UPDATE Administradores SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
            f"ultimo_acceso = {ahora} WHERE id = ?", (admin_id,)
        )

    def verificar_credenciales(self, usuario, password):
        """Verifica el usuario y la contraseña introducidos."""
        admin = self.obtener_por_usuario(usuario)
        if not admin:
            return None

        password_hash = admin.get("password_hash")
        if not password_hash:
            return None

        if security.check_password_hash(password_hash, password):
            return admin
        return None