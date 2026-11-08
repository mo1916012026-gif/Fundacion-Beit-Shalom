"""Configuración de la aplicación. Todo valor sensible viene del archivo .env"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(nombre, defecto=False):
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in ("1", "true", "yes", "si", "sí")


class Config:
    DEBUG = _bool("FLASK_DEBUG", False)

    SECRET_KEY = os.getenv("SECRET_KEY") or ("clave-solo-para-desarrollo" if DEBUG else None)

    # Sesiones y cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("COOKIES_SEGURAS", False)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    MAX_CONTENT_LENGTH = 64 * 1024  # 64 KB: un formulario legítimo pesa mucho menos
    WTF_CSRF_TIME_LIMIT = 3600

    # Carpeta con las páginas HTML del sitio de la fundación (la sirve Flask)
    SITIO_DIR = Path(__file__).resolve().parent / "sitio"
    SITIO_URL = os.getenv("SITIO_URL", "/")

    # Límite de envíos del formulario público por IP
    REGISTROS_MAX = 5
    REGISTROS_VENTANA_SEG = 600

    # Base de datos
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    DB_SERVER = os.getenv("DB_SERVER", "localhost")
    DB_NAME = os.getenv("DB_NAME", "BeitShalomDB")
    DB_USER = os.getenv("DB_USER", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_TRUSTED = _bool("DB_TRUSTED", False)
    DB_ENCRYPT = os.getenv("DB_ENCRYPT", "yes")
    DB_TRUST_CERT = os.getenv("DB_TRUST_CERT", "no")
    DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "10"))

    @classmethod
    def validar(cls):
        if not cls.SECRET_KEY:
            raise RuntimeError(
                "Falta SECRET_KEY en el archivo .env. Genera una con: "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
