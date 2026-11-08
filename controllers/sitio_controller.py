"""Controlador del sitio: entrega las páginas HTML y los recursos de la fundación.

Así el menú del sitio (index.html y demás páginas) y los formularios conviven en
el mismo servidor y el mismo dominio.
"""
from pathlib import PurePosixPath

from flask import Blueprint, abort, current_app, send_from_directory

sitio_bp = Blueprint("sitio", __name__)

# Solo se entregan estos tipos de archivo: nunca código Python, .env, etc.
EXTENSIONES_PERMITIDAS = {
    ".html", ".css", ".js", ".map", ".json", ".webmanifest", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp4", ".webm", ".pdf",
}


@sitio_bp.route("/")
def inicio():
    return send_from_directory(current_app.config["SITIO_DIR"], "index.html")


@sitio_bp.route("/<path:ruta>")
def archivo(ruta):
    if PurePosixPath(ruta).suffix.lower() not in EXTENSIONES_PERMITIDAS:
        abort(404)
    # send_from_directory rechaza rutas que intenten salir de la carpeta (../)
    return send_from_directory(current_app.config["SITIO_DIR"], ruta)
