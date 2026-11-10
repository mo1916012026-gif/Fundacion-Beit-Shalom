"""Punto de entrada: crea la aplicación Flask y registra los controladores."""
import logging

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError, CSRFProtect  # type: ignore

from config import Config
from controllers.admin_controller import admin_bp
from controllers.colaborador_controller import colaborador_bp
from controllers.sitio_controller import sitio_bp
from database import inicializar_db

csrf = CSRFProtect()


def create_app():
    Config.validar()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf.init_app(app)

    # Crear tablas automáticamente en la base de datos conectada (Render/Local)
    with app.app_context():
        try:
            inicializar_db()
        except Exception as e:
            logging.error(f"Error al inicializar la base de datos: {e}")

    app.register_blueprint(colaborador_bp)
    app.register_blueprint(admin_bp)
    # El sitio va al final: sus rutas comodín no deben tapar /registro ni /admin
    app.register_blueprint(sitio_bp)

    @app.context_processor
    def variables_globales():
        return {"sitio_url": app.config["SITIO_URL"]}

    @app.after_request
    def cabeceras_de_seguridad(respuesta):
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["X-Referrer-Policy"] = "same-origin"
        if request.blueprint != "sitio":
            # Formularios y panel: política estricta (solo scripts propios) y sin caché
            respuesta.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data:; script-src 'self'; "
                "frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
            )
            respuesta.headers.setdefault("Cache-Control", "no-store")
        return respuesta

    @app.errorhandler(CSRFError)
    def error_csrf(_):
        return render_template("error.html", titulo="La página expiró",
                                mensaje="Por seguridad, la página caducó. "
                                        "Vuelve al formulario e inténtalo de nuevo."), 400

    @app.errorhandler(400)
    def solicitud_invalida(_):
        return render_template("error.html", titulo="Solicitud no válida",
                                mensaje="Los datos enviados no son válidos."), 400

    @app.errorhandler(404)
    def no_encontrado(_):
        return render_template("error.html", titulo="Página no encontrada",
                                mensaje="La página que buscas no existe."), 404

    @app.errorhandler(413)
    def demasiado_grande(_):
        return render_template("error.html", titulo="Solicitud demasiado grande",
                                mensaje="Los datos enviados superan el tamaño permitido."), 413

    @app.errorhandler(500)
    def error_interno(_):
        return render_template("error.html", titulo="Error del servidor",
                                mensaje="Ocurrió un error inesperado. Intenta de nuevo."), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=Config.DEBUG)