"""Pruebas de la aplicación SIN SQL Server: los repositorios se reemplazan por otros en memoria.
Uso:  python tests/test_app.py"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.update(SECRET_KEY="x" * 32, FLASK_DEBUG="0")

import fakes  # noqa: E402  (prepara pyodbc falso si hace falta)
import controllers.admin_controller as ac  # noqa: E402
import controllers.colaborador_controller as cc  # noqa: E402
from app import create_app  # noqa: E402

BUENOS = dict(nombre="Ana María Pérez", pais="El Salvador", correo="Ana@Correo.com",
              telefono="+503 7777 8888", modalidad="Virtual", disponibilidad="Ocasional",
              motivacion="Quiero ayudar", areas=["1", "3"], privacidad="1")


def token(cliente, url):
    html = cliente.get(url).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def nueva_app():
    repo = fakes.FakeColaboradores()
    cc.repositorio = repo
    ac.colaboradores = repo
    ac.administradores = fakes.FakeAdmin()
    cc._envios.clear()
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = True
    return app, repo


def probar_sitio(app):
    c = app.test_client()
    r = c.get("/")
    assert r.status_code == 200 and b"Fundaci" in r.data
    assert b'href="/registro">Colaborar' in r.data, "el menú debe tener 'Colaborar'"
    assert "Content-Security-Policy" not in r.headers, "el sitio no lleva la CSP estricta"
    for ruta in ("/about.html", "/contact.html", "/assets/css/kidearn.css",
                 "/assets/images/logo-fundacion.png"):
        assert c.get(ruta).status_code == 200, ruta
    for ruta in ("/app.py", "/config.py", "/.env", "/../.env", "/assets/../../.env",
                 "/sql/01_base_de_datos.sql", "/inc/sendemail.php"):
        assert c.get(ruta).status_code == 404, ruta
    assert c.get("/registro").status_code == 200, "/registro no debe taparlo el comodín del sitio"


def probar_registro_publico(app, repo):
    c = app.test_client()
    r = c.get("/registro")
    assert r.status_code == 200 and "frame-ancestors" in r.headers["Content-Security-Policy"]
    assert b'href="/registro">Colaborar' in r.data, "el menú del sitio aparece en el formulario"
    assert c.post("/registro", data=BUENOS).status_code == 400, "sin CSRF debe rechazarse"
    t = token(c, "/registro")
    r = c.post("/registro", data={**BUENOS, "csrf_token": t})
    assert r.status_code == 302, r.status_code
    assert repo.filas[1]["correo"] == "ana@correo.com" and repo.filas[1]["areas_ids"] == [1, 3]
    assert c.get("/confirmacion").status_code == 200
    assert c.get("/confirmacion").status_code == 302, "confirmación solo una vez"
    r = c.post("/registro", data={**BUENOS, "csrf_token": t})
    assert r.status_code == 409 and "ya tiene" in r.get_data(as_text=True)
    r = c.post("/registro", data={"csrf_token": t})
    assert r.status_code == 400 and r.get_data(as_text=True).count('class="error"') >= 8
    r = c.post("/registro", data={**BUENOS, "correo": "otro@x.co", "areas": ["99"], "csrf_token": t})
    assert r.status_code == 400
    r = c.post("/registro", data={**BUENOS, "nombre": "<script>alert(1)</script>", "csrf_token": t})
    assert r.status_code == 400 and "<script>alert" not in r.get_data(as_text=True)
    r = c.post("/registro", data={**BUENOS, "sitio_web": "bot", "csrf_token": t})
    assert r.status_code == 302 and len(repo.filas) == 1, "los bots no guardan nada"
    for _ in range(6):
        ultimo = c.post("/registro", data={"csrf_token": t}).status_code
    assert ultimo == 429, ultimo


def probar_admin_crud(app, repo):
    a = app.test_client()
    # Rutas protegidas
    for ruta in ("/admin/", "/admin", "/admin/colaboradores", "/admin/colaboradores/nuevo",
                 "/admin/colaboradores/1/editar", "/admin/colaboradores/1/eliminar", "/admin/exportar"):
        assert a.get(ruta).status_code == 302, ruta
    # Login
    t = token(a, "/admin/login")
    assert a.post("/admin/login", data={"usuario": "admin", "clave": "mala", "csrf_token": t}).status_code == 401
    r = a.post("/admin/login?siguiente=https://evil.com",
               data={"usuario": "admin", "clave": "claveSegura123", "csrf_token": t})
    assert r.status_code == 302 and r.headers["Location"] in ("/admin", "/admin/"), r.headers["Location"]
    for ruta in ("/admin/", "/admin", "/admin/colaboradores", "/admin/colaboradores/nuevo"):
        assert a.get(ruta, follow_redirects=True).status_code == 200, ruta

    # CREATE desde el panel
    t = token(a, "/admin/colaboradores/nuevo")
    datos = {**BUENOS, "correo": "luis@correo.com", "nombre": "Luis Hernández", "csrf_token": t}
    r = a.post("/admin/colaboradores/nuevo", data=datos)
    assert r.status_code == 302 and "/admin/colaboradores/2" in r.headers["Location"], r.headers
    r = a.post("/admin/colaboradores/nuevo", data=datos)
    assert r.status_code == 409, "correo duplicado"
    r = a.post("/admin/colaboradores/nuevo", data={**datos, "correo": "mal", "areas": []})
    assert r.status_code == 400 and "al menos un área" in r.get_data(as_text=True)

    # READ
    for ruta in ("/admin/colaboradores", "/admin/colaboradores/1", "/admin/colaboradores/2"):
        assert a.get(ruta).status_code == 200, ruta
    assert a.get("/admin/colaboradores/99").status_code == 404
    repo.filas[1]["motivacion"] = "<b>hola</b>"
    assert "&lt;b&gt;hola" in a.get("/admin/colaboradores/1").get_data(as_text=True)

    # UPDATE
    html = a.get("/admin/colaboradores/2/editar").get_data(as_text=True)
    assert 'value="Luis Hernández"' in html and "luis@correo.com" in html
    assert len(re.findall(r'name="areas" value="\d+"\s+checked', html)) == 2, "áreas marcadas"
    t = token(a, "/admin/colaboradores/2/editar")
    r = a.post("/admin/colaboradores/2/editar",
               data={**datos, "nombre": "Luis Alberto Hernández", "areas": ["2"], "csrf_token": t})
    assert r.status_code == 302
    assert repo.filas[2]["nombre_completo"] == "Luis Alberto Hernández" and repo.filas[2]["areas_ids"] == [2]
    r = a.post("/admin/colaboradores/2/editar", data={**datos, "correo": "ana@correo.com", "csrf_token": t})
    assert r.status_code == 409, "no se puede usar el correo de otra persona"
    r = a.post("/admin/colaboradores/2/editar", data={**datos, "pais": "Narnia", "csrf_token": t})
    assert r.status_code == 400
    assert a.post("/admin/colaboradores/99/editar", data={**datos, "csrf_token": t}).status_code == 404
    # Cambiar estado
    assert a.post("/admin/colaboradores/1", data={"estado": "Aprobado", "csrf_token": t}).status_code == 302
    assert repo.filas[1]["estado"] == "Aprobado"
    assert a.post("/admin/colaboradores/1", data={"estado": "Hackeado", "csrf_token": t}).status_code == 400

    # Exportar
    x = a.get("/admin/exportar")
    assert x.status_code == 200 and x.data[:2] == b"PK"
    import openpyxl
    repo.filas[1]["nombre_completo"] = "=CMD Prueba"
    x = a.get("/admin/exportar")
    assert openpyxl.load_workbook(io.BytesIO(x.data)).active["B2"].value.startswith("'="), "fórmula neutralizada"

    # DELETE: confirmación (GET) y borrado (POST)
    assert "no se puede deshacer" in a.get("/admin/colaboradores/2/eliminar").get_data(as_text=True)
    assert 2 in repo.filas, "el GET no borra nada"
    assert a.post("/admin/colaboradores/2/eliminar", data={}).status_code == 400, "sin CSRF"
    r = a.post("/admin/colaboradores/2/eliminar", data={"csrf_token": t})
    assert r.status_code == 302 and 2 not in repo.filas
    assert a.get("/admin/colaboradores/2").status_code == 404
    assert a.post("/admin/colaboradores/2/eliminar", data={"csrf_token": t}).status_code == 404
    # Cerrar sesión
    a.get("/admin/logout")
    assert a.get("/admin/colaboradores").status_code == 302


if __name__ == "__main__":
    app, repo = nueva_app()
    probar_sitio(app)
    probar_registro_publico(app, repo)
    probar_admin_crud(app, repo)
    print("TODAS LAS PRUEBAS PASARON")
