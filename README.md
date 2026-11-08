# Fundación Beit Shalom · Sitio web + Registro de colaboradores

Python · Flask · POO · Arquitectura MVC · SQL Server (pyodbc) · HTML/CSS/JS

Un solo servidor entrega el **sitio de la fundación** (`sitio/`, con su menú) y los **formularios**:
el menú del sitio tiene la opción **Colaborar → Quiero colaborar / Acceso administrador**.

## Arquitectura MVC

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Modelo | `models/` | Clase `Colaborador` (POO: atributos privados, propiedades, `validar()`) |
| Acceso a datos | `repositories/` | `BaseRepository` (clase base) → `ColaboradorRepository`, `AdminRepository`. Único lugar con SQL |
| Controlador | `controllers/` | Rutas: `sitio`, `colaborador` (registro público), `admin` (panel y CRUD) |
| Vista | `templates/`, `static/` | Plantillas Jinja2 con el diseño del sitio, CSS y validaciones JS |

Otros: `app.py` (crea la app), `config.py` (lee `.env`), `database.py` (conexión y transacciones), `sql/` (scripts), `tests/`.

## CRUD de colaboradores

| Operación | Dónde |
|---|---|
| Crear | `/registro` (público) y `/admin/colaboradores/nuevo` |
| Leer | `/admin/colaboradores` (filtros, paginación, Excel) y `/admin/colaboradores/<id>` |
| Actualizar | `/admin/colaboradores/<id>/editar` y cambio de estado en el detalle |
| Eliminar | `/admin/colaboradores/<id>/eliminar` (pide confirmación) |

## Requisitos
- Windows con Python 3.10+ y VS Code
- SQL Server 2017+ (o Express) y **ODBC Driver 17 o 18 for SQL Server**
- Librerías: `requirements.txt` (Flask, Flask-WTF, pyodbc, python-dotenv, openpyxl, waitress)

## Instalación
1. En SSMS ejecuta `sql/01_base_de_datos.sql` (crea `BeitShalomDB`, tablas, llaves y áreas).
   Opcional, si usarás usuario SQL en vez de Windows: `sql/02_usuario_aplicacion.sql` (cambia antes la contraseña).
   Si ya habías ejecutado una versión anterior del 02, ejecuta `sql/03_permisos_crud.sql`.
2. En la terminal, dentro de esta carpeta:
   ```
   python -m venv venv
   .\venv\Scripts\Activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
3. Edita `.env` (tabla abajo).
4. Crea un administrador: `python crear_admin.py` (puede insertarlo directo en la base).
5. `python app.py` y abre **http://127.0.0.1:5000/** (no abras `index.html` con doble clic: los formularios necesitan el servidor).

## Variables de `.env`
| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave de sesión. `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_DEBUG` | `1` en desarrollo, `0` en producción |
| `COOKIES_SEGURAS` | `1` solo con HTTPS |
| `SITIO_URL` | Destino del botón "Volver al sitio" (`/`) |
| `DB_DRIVER` | `ODBC Driver 17 for SQL Server` o `18` |
| `DB_SERVER` | `localhost\SQLEXPRESS`, o `IP,1433` |
| `DB_NAME` | `BeitShalomDB` |
| `DB_TRUSTED` | `1` = login de Windows; `0` = usar `DB_USER` y `DB_PASSWORD` |
| `DB_USER`, `DB_PASSWORD` | Usuario SQL (p. ej. `beitshalom_app`) |
| `DB_ENCRYPT`, `DB_TRUST_CERT` | Cifrado de la conexión (`no`/`yes` en local) |

## Base de datos
`Colaboradores` 1—N `ColaboradorAreas` N—1 `AreasColaboracion` (relación muchos a muchos, con PK, FK, UNIQUE y CHECK);
`Administradores` para el login (contraseñas con hash). Las reglas también existen en SQL, no solo en Python.

## Seguridad y validaciones
Validación en tres capas (navegador → Python → SQL), consultas parametrizadas, transacciones, CSRF, cabeceras CSP,
campo anti-bots, límite de envíos por IP, bloqueo tras 5 intentos fallidos de login, sesión de 30 min y manejo de errores
con páginas amigables (la aplicación no se cae ante datos inválidos o fallos de la base).

## Pruebas (no necesitan SQL Server)
```
python tests/test_app.py
python tests/test_repositorios.py
```

## Antes de publicar
`FLASK_DEBUG=0`, `COOKIES_SEGURAS=1` con HTTPS y `waitress-serve --listen=127.0.0.1:8000 app:app` detrás de IIS/Nginx.

## Git
`venv/`, `.env` y `__pycache__/` están en `.gitignore`. Haz commits pequeños y descriptivos, por ejemplo:
`git add -A && git commit -m "feat: editar y eliminar colaboradores"`.
