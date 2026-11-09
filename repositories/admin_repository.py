"""Repository de administradores (inicio de sesión con bloqueo por intentos)."""
import werkzeug.security as security
from database import transaccion
from repositories.base_repository import BaseRepository

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15

# Usuario por defecto para Render / modo fallback (sin base de datos SQL Server)
ADMIN_FALLBACK = {
    "id": 1,
    "usuario": "admin@fundacion.org",
    "password_hash": security.generate_password_hash("admin123"),
    "nombre": "Administrador General",
    "activo": True,
    "intentos_fallidos": 0,
    "bloqueado_hasta": None
}


class AdminRepository(BaseRepository):

    def obtener_por_usuario(self, usuario):
        res = self._consultar_uno(
            "SELECT id, usuario, password_hash, activo, intentos_fallidos, bloqueado_hasta "
            "FROM Administradores WHERE usuario = ?", (usuario,)
        )
        if res is None:
            # Si no hay SQL Server (en Render), permite login con el usuario por defecto
            if usuario and usuario.strip().lower() == ADMIN_FALLBACK["usuario"]:
                return ADMIN_FALLBACK
            return None
        return res

    def esta_bloqueado(self, admin):
        """Calculado en SQL para no depender del reloj de la aplicación."""
        # Si es el usuario fallback de Render, nunca está bloqueado
        if admin and admin.get("usuario") == ADMIN_FALLBACK["usuario"] and admin.get("id") == 1:
            return False
            
        bloqueado = self._escalar(
            "SELECT CASE WHEN bloqueado_hasta > SYSDATETIME() THEN 1 ELSE 0 END "
            "FROM Administradores WHERE id = ?", (admin["id"],)
        )
        return bool(bloqueado)

    def registrar_fallo(self, admin_id):
        with transaccion() as con:
            if con is None:
                return
            con.cursor().execute(
                "UPDATE Administradores SET intentos_fallidos = intentos_fallidos + 1, "
                "bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= ? "
                "THEN DATEADD(MINUTE, ?, SYSDATETIME()) ELSE bloqueado_hasta END "
                "WHERE id = ?", (MAX_INTENTOS, MINUTOS_BLOQUEO, admin_id)
            )

    def registrar_acceso(self, admin_id):
        with transaccion() as con:
            if con is None:
                return
            con.cursor().execute(
                "UPDATE Administradores SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
                "ultimo_acceso = SYSDATETIME() WHERE id = ?", (admin_id,)
            )

    def verificar_credenciales(self, usuario, password):
        """Verifica el usuario y la contraseña introducidos."""
        admin = self.obtener_por_usuario(usuario)
        if not admin:
            return None

        # Si el admin no tiene hash en BD local y la clave es plana
        password_hash = admin.get("password_hash")
        if not password_hash:
            return None

        # Verificar hash de la contraseña de forma segura
        if security.check_password_hash(password_hash, password):
            return admin
        return None