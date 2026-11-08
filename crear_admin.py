"""Crea un administrador del panel. La contraseña nunca se guarda en texto plano, solo su hash.
Uso:  python crear_admin.py
Puede insertar el administrador directamente en la base (usa la conexión del archivo .env)
o imprimir el INSERT para ejecutarlo a mano en SSMS."""
import getpass
import re

from werkzeug.security import generate_password_hash

usuario = input("Nombre de usuario (mínimo 4 caracteres, sin espacios): ").strip()
if not re.fullmatch(r"[A-Za-z0-9._-]{4,50}", usuario):
    raise SystemExit("Usuario no válido.")

clave = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
if len(clave) < 12 or clave != getpass.getpass("Repite la contraseña: "):
    raise SystemExit("La contraseña debe tener 12+ caracteres y coincidir en ambas entradas.")

hash_clave = generate_password_hash(clave)

if input("¿Insertarlo ahora en la base de datos? (s/n): ").strip().lower() == "s":
    from database import transaccion
    try:
        with transaccion() as con:
            con.cursor().execute(
                "INSERT INTO Administradores (usuario, password_hash) VALUES (?, ?)",
                (usuario, hash_clave))
        print("Administrador creado. Ya puedes entrar en http://127.0.0.1:5000/admin/login")
    except Exception as error:
        raise SystemExit(f"No se pudo insertar ({error}). Usa el INSERT de abajo en SSMS.")
else:
    print("\nEjecuta esto en SQL Server Management Studio (base BeitShalomDB):\n")
    print("INSERT INTO Administradores (usuario, password_hash)")
    print(f"VALUES (N'{usuario}', N'{hash_clave}');")
