"""Controlador público: recibe el formulario, valida y coordina el guardado."""
import logging
import time
from collections import defaultdict, deque

from flask import (Blueprint, current_app, redirect, render_template, request,
                   session, url_for)

from controllers.contexto import contexto_formulario
from models.colaborador import Colaborador
from repositories.colaborador_repository import (ColaboradorRepository,
                                                 CorreoDuplicadoError)

logger = logging.getLogger(__name__)
colaborador_bp = Blueprint("colaborador", __name__)
repositorio = ColaboradorRepository()

# Control sencillo de envíos por IP (se reinicia al reiniciar la aplicación)
_envios = defaultdict(deque)


def _limite_excedido():
    ahora = time.time()
    cola = _envios[request.remote_addr]
    ventana = current_app.config["REGISTROS_VENTANA_SEG"]
    while cola and ahora - cola[0] > ventana:
        cola.popleft()
    if len(cola) >= current_app.config["REGISTROS_MAX"]:
        return True
    cola.append(ahora)
    return False


def _formulario(areas, datos=None, errores=None, codigo=200):
    return render_template("registro.html",
                           **contexto_formulario(areas, datos, errores)), codigo


@colaborador_bp.route("/registro", methods=["GET", "POST"])
def registrar():
    try:
        areas = repositorio.obtener_areas_activas()
    except Exception:
        logger.exception("No se pudo consultar las áreas en SQL Server")
        return render_template("error.html", titulo="Servicio no disponible",
                               mensaje="Estamos teniendo un problema técnico. "
                                       "Por favor intenta de nuevo en unos minutos."), 503

    if request.method == "GET":
        return _formulario(areas)

    # Campo trampa para bots: las personas no lo ven, los bots sí lo llenan
    if request.form.get("sitio_web"):
        session["registro_ok"] = True
        return redirect(url_for("colaborador.confirmacion"))

    if _limite_excedido():
        return render_template("error.html", titulo="Demasiados intentos",
                               mensaje="Has enviado varias solicitudes seguidas. "
                                       "Espera unos minutos e inténtalo de nuevo."), 429

    colaborador = Colaborador.desde_formulario(request.form)
    errores = colaborador.validar(areas_validas=[a["id"] for a in areas])
    if errores:
        return _formulario(areas, colaborador.a_diccionario(), errores, 400)

    try:
        repositorio.guardar(colaborador)
    except CorreoDuplicadoError:
        errores["correo"] = "Este correo ya tiene una solicitud registrada."
        return _formulario(areas, colaborador.a_diccionario(), errores, 409)
    except Exception:
        logger.exception("Error al guardar el colaborador")
        errores["general"] = "No pudimos guardar tu solicitud. Intenta de nuevo en unos minutos."
        return _formulario(areas, colaborador.a_diccionario(), errores, 500)

    session["registro_ok"] = True
    return redirect(url_for("colaborador.confirmacion"))


@colaborador_bp.route("/confirmacion")
def confirmacion():
    if not session.pop("registro_ok", None):
        return redirect(url_for("colaborador.registrar"))
    return render_template("confirmacion.html")
