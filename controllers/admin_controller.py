"""Controlador del panel administrativo (acceso solo para personal autorizado)."""
import io
import logging
from functools import wraps
from urllib.parse import urlparse

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)
from openpyxl import Workbook
from openpyxl.styles import Font
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from controllers.contexto import contexto_formulario
from models.colaborador import ESTADOS, Colaborador
from repositories.admin_repository import AdminRepository
from repositories.colaborador_repository import (ColaboradorRepository,
                                                 CorreoDuplicadoError)

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
colaboradores = ColaboradorRepository()
administradores = AdminRepository()

# Hash falso para que el tiempo de respuesta sea igual si el usuario no existe
_HASH_FALSO = generate_password_hash("contraseña-inexistente")
POR_PAGINA = 15


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login", siguiente=request.path))
        return vista(*args, **kwargs)
    return envoltura


def _destino_seguro(destino):
    """Evita redirecciones a sitios externos (open redirect)."""
    if destino and destino.startswith("/admin") and not urlparse(destino).netloc:
        return destino
    return url_for("admin.dashboard")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()[:50]
        clave = request.form.get("clave") or ""
        mensaje = "Usuario o contraseña incorrectos."
        try:
            admin = administradores.obtener_por_usuario(usuario)
            if admin is None:
                check_password_hash(_HASH_FALSO, clave)
            elif not admin["activo"]:
                check_password_hash(_HASH_FALSO, clave)
            elif administradores.esta_bloqueado(admin):
                mensaje = "Cuenta bloqueada temporalmente por varios intentos fallidos."
            elif check_password_hash(admin["password_hash"], clave):
                administradores.registrar_acceso(admin["id"])
                session.clear()
                session.permanent = True
                session["admin_id"] = admin["id"]
                session["admin_usuario"] = admin["usuario"]
                return redirect(_destino_seguro(request.args.get("siguiente")))
            else:
                administradores.registrar_fallo(admin["id"])
        except Exception:
            logger.exception("Error en el inicio de sesión")
            mensaje = "No se pudo verificar el acceso. Intenta de nuevo."
        flash(mensaje, "error")
        return render_template("admin/login.html"), 401
    return render_template("admin/login.html")

@admin_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_bp.route("", strict_slashes=False)
@login_requerido
def dashboard():
    return render_template("admin/dashboard.html", datos=colaboradores.estadisticas())


def _filtros_desde_url():
    area = request.args.get("area", "")
    estado = request.args.get("estado", "")
    return {
        "busqueda": (request.args.get("q") or "").strip()[:100],
        "pais": (request.args.get("pais") or "").strip()[:80],
        "area_id": int(area) if area.isdigit() and len(area) <= 9 else None,
        "estado": estado if estado in ESTADOS else "",
    }


@admin_bp.route("/colaboradores")
@login_requerido
def listado():
    filtros = _filtros_desde_url()
    pagina = request.args.get("pagina", "1")
    pagina = int(pagina) if pagina.isdigit() and 0 < int(pagina) < 100000 else 1
    filas, total = colaboradores.listar(pagina=pagina, por_pagina=POR_PAGINA, **filtros)
    paginas = max(1, -(-total // POR_PAGINA))
    return render_template(
        "admin/listado.html", filas=filas, total=total, pagina=pagina, paginas=paginas,
        filtros=filtros, estados=ESTADOS, paises=colaboradores.paises_registrados(),
        areas=colaboradores.obtener_areas_activas(),
        args={k: v for k, v in request.args.items() if k != "pagina" and v},
    )


@admin_bp.route("/colaboradores/<int:colaborador_id>", methods=["GET", "POST"])
@login_requerido
def detalle(colaborador_id):
    if request.method == "POST":
        estado = request.form.get("estado", "")
        if estado not in ESTADOS:
            abort(400)
        if not colaboradores.cambiar_estado(colaborador_id, estado):
            abort(404)
        flash(f"Estado actualizado a «{estado}».", "ok")
        return redirect(url_for("admin.detalle", colaborador_id=colaborador_id))
    persona = colaboradores.obtener(colaborador_id)
    if persona is None:
        abort(404)
    return render_template("admin/detalle.html", p=persona, estados=ESTADOS)


def _formulario_admin(titulo, accion, areas, datos=None, errores=None, codigo=200):
    return render_template("admin/formulario.html", titulo=titulo, accion=accion,
                           **contexto_formulario(areas, datos, errores)), codigo


def _guardar_desde_formulario(areas, titulo, accion, colaborador_id=None):
    """Valida el formulario y crea (sin id) o actualiza (con id) al colaborador.
    Devuelve (respuesta_a_mostrar, None) si hubo un problema, o (None, id) si se guardó."""
    colaborador = Colaborador.desde_formulario(request.form)
    errores = colaborador.validar(areas_validas=[a["id"] for a in areas])
    if errores:
        return _formulario_admin(titulo, accion, areas, colaborador.a_diccionario(),
                                 errores, 400), None
    try:
        if colaborador_id is None:
            colaborador_id = colaboradores.guardar(colaborador)
        elif not colaboradores.actualizar(colaborador_id, colaborador):
            abort(404)
    except CorreoDuplicadoError:
        errores["correo"] = "Ese correo ya está registrado en otro colaborador."
        return _formulario_admin(titulo, accion, areas, colaborador.a_diccionario(),
                                 errores, 409), None
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error al guardar el colaborador desde el panel")
        errores["general"] = "No se pudo guardar. Intenta de nuevo."
        return _formulario_admin(titulo, accion, areas, colaborador.a_diccionario(),
                                 errores, 500), None
    return None, colaborador_id


@admin_bp.route("/colaboradores/nuevo", methods=["GET", "POST"])
@login_requerido
def nuevo():
    """CREATE desde el panel (el público usa /registro)."""
    areas = colaboradores.obtener_areas_activas()
    accion = url_for("admin.nuevo")
    if request.method == "GET":
        return _formulario_admin("Nuevo colaborador", accion, areas)
    respuesta, nuevo_id = _guardar_desde_formulario(areas, "Nuevo colaborador", accion)
    if respuesta:
        return respuesta
    flash("Colaborador registrado correctamente.", "ok")
    return redirect(url_for("admin.detalle", colaborador_id=nuevo_id))


@admin_bp.route("/colaboradores/<int:colaborador_id>/editar", methods=["GET", "POST"])
@login_requerido
def editar(colaborador_id):
    """UPDATE de todos los datos del colaborador."""
    persona = colaboradores.obtener(colaborador_id)
    if persona is None:
        abort(404)
    areas = colaboradores.obtener_areas_activas()
    accion = url_for("admin.editar", colaborador_id=colaborador_id)
    titulo = "Editar colaborador"
    if request.method == "GET":
        datos = {
            "nombre": persona["nombre_completo"], "pais": persona["pais"],
            "correo": persona["correo"], "telefono": persona["telefono"] or "",
            "modalidad": persona["modalidad"], "disponibilidad": persona["disponibilidad"],
            "motivacion": persona["motivacion"] or "", "areas": persona["areas_ids"],
            "privacidad": True,
        }
        return _formulario_admin(titulo, accion, areas, datos)
    respuesta, _ = _guardar_desde_formulario(areas, titulo, accion, colaborador_id)
    if respuesta:
        return respuesta
    flash("Datos actualizados correctamente.", "ok")
    return redirect(url_for("admin.detalle", colaborador_id=colaborador_id))


@admin_bp.route("/colaboradores/<int:colaborador_id>/eliminar", methods=["GET", "POST"])
@login_requerido
def eliminar(colaborador_id):
    """DELETE: primero una pantalla de confirmación (GET) y luego el borrado (POST)."""
    persona = colaboradores.obtener(colaborador_id)
    if persona is None:
        abort(404)
    if request.method == "POST":
        if not colaboradores.eliminar(colaborador_id):
            abort(404)
        flash(f"Se eliminó a «{persona['nombre_completo']}».", "ok")
        return redirect(url_for("admin.listado"))
    return render_template("admin/eliminar.html", p=persona)


def _seguro_para_excel(valor):
    """Evita 'inyección de fórmulas': un texto que empieza con = + - @ se ejecutaría en Excel."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


@admin_bp.route("/exportar")
@login_requerido
def exportar():
    filas = colaboradores.listar_todos(**_filtros_desde_url())
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Colaboradores"
    encabezados = ["ID", "Nombre", "País", "Correo", "Teléfono", "Modalidad",
                   "Disponibilidad", "Áreas", "Estado", "Fecha de registro"]
    hoja.append(encabezados)
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for f in filas:
        hoja.append([_seguro_para_excel(v) for v in (
            f["id"], f["nombre_completo"], f["pais"], f["correo"], f["telefono"] or "",
            f["modalidad"], f["disponibilidad"], f["areas"] or "", f["estado"],
            f["fecha_registro"].strftime("%Y-%m-%d %H:%M"))])
    for columna, ancho in zip("ABCDEFGHIJ", (6, 30, 16, 32, 18, 14, 20, 45, 14, 18)):
        hoja.column_dimensions[columna].width = ancho
    memoria = io.BytesIO()
    libro.save(memoria)
    memoria.seek(0)
    return send_file(memoria, as_attachment=True, download_name="colaboradores_beit_shalom.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
