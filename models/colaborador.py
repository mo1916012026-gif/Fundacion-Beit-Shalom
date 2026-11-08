"""Modelo Colaborador: representa una solicitud y aplica las reglas del negocio."""
import re

PAISES = [
    "El Salvador", "Guatemala", "Honduras", "Nicaragua", "Costa Rica", "Panamá",
    "México", "Colombia", "Venezuela", "Ecuador", "Perú", "Bolivia", "Chile",
    "Argentina", "Uruguay", "Paraguay", "Brasil", "República Dominicana",
    "Cuba", "Puerto Rico", "Estados Unidos", "Canadá", "España", "Otro",
]
MODALIDADES = ("Presencial", "Virtual", "Ambas")
DISPONIBILIDADES = ("Entre semana", "Fines de semana", "Horarios flexibles", "Ocasional")
ESTADOS = ("Pendiente", "En revisión", "Aprobado", "Rechazado")

# Estas expresiones se repiten en static/js/validaciones.js (experiencia del usuario),
# pero la validación que cuenta es esta, la del servidor.
_RE_NOMBRE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .\-]+")
_RE_CORREO = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_RE_TELEFONO = re.compile(r"\+?[0-9\s()\-]{7,30}")
_RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _limpiar(valor, una_linea=True):
    """Convierte a texto, quita caracteres de control y espacios sobrantes."""
    texto = _RE_CONTROL.sub("", str(valor or "")).strip()
    if una_linea:
        texto = re.sub(r"\s+", " ", texto)
    return texto


class Colaborador:
    """Cada solicitud recibida es un objeto de esta clase.

    Encapsulamiento: los atributos son privados (_nombre, _correo...) y se
    acceden mediante propiedades que limpian y normalizan el dato al asignarlo.
    """

    def __init__(self, nombre="", pais="", correo="", telefono="",
                 modalidad="", disponibilidad="", motivacion="",
                 areas=None, acepta_privacidad=False):
        self.nombre = nombre
        self.pais = pais
        self.correo = correo
        self.telefono = telefono
        self.modalidad = modalidad
        self.disponibilidad = disponibilidad
        self.motivacion = motivacion
        self.areas = areas
        self.acepta_privacidad = acepta_privacidad

    @classmethod
    def desde_formulario(cls, formulario):
        """Crea un Colaborador a partir de los datos de un formulario HTML.
        'formulario' puede ser cualquier objeto con .get() y .getlist()."""
        return cls(
            nombre=formulario.get("nombre"),
            pais=formulario.get("pais"),
            correo=formulario.get("correo"),
            telefono=formulario.get("telefono"),
            modalidad=formulario.get("modalidad"),
            disponibilidad=formulario.get("disponibilidad"),
            motivacion=formulario.get("motivacion"),
            areas=formulario.getlist("areas"),
            acepta_privacidad=formulario.get("privacidad") == "1",
        )

    # ---------- Propiedades (encapsulamiento) ----------
    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, valor):
        self._nombre = _limpiar(valor)

    @property
    def pais(self):
        return self._pais

    @pais.setter
    def pais(self, valor):
        self._pais = _limpiar(valor)

    @property
    def correo(self):
        return self._correo

    @correo.setter
    def correo(self, valor):
        self._correo = _limpiar(valor).lower()

    @property
    def telefono(self):
        return self._telefono

    @telefono.setter
    def telefono(self, valor):
        self._telefono = _limpiar(valor)

    @property
    def modalidad(self):
        return self._modalidad

    @modalidad.setter
    def modalidad(self, valor):
        self._modalidad = _limpiar(valor)

    @property
    def disponibilidad(self):
        return self._disponibilidad

    @disponibilidad.setter
    def disponibilidad(self, valor):
        self._disponibilidad = _limpiar(valor)

    @property
    def motivacion(self):
        return self._motivacion

    @motivacion.setter
    def motivacion(self, valor):
        self._motivacion = _limpiar(valor, una_linea=False)

    @property
    def areas(self):
        return list(self._areas)

    @areas.setter
    def areas(self, valores):
        ids = set()
        for v in valores or []:
            texto = str(v).strip()
            if texto.isdigit() and len(texto) <= 9:
                ids.add(int(texto))
        self._areas = sorted(ids)

    @property
    def acepta_privacidad(self):
        return self._acepta_privacidad

    @acepta_privacidad.setter
    def acepta_privacidad(self, valor):
        self._acepta_privacidad = valor is True

    # ---------- Reglas de negocio ----------
    def validar(self, areas_validas=None):
        """Devuelve un diccionario {campo: mensaje}. Vacío = todo correcto."""
        errores = {}

        if len(self.nombre) < 5 or len(self.nombre) > 150:
            errores["nombre"] = "Ingresa tu nombre completo (entre 5 y 150 caracteres)."
        elif not _RE_NOMBRE.fullmatch(self.nombre):
            errores["nombre"] = "El nombre solo puede contener letras, espacios, guiones y apóstrofes."

        if self.pais not in PAISES:
            errores["pais"] = "Selecciona un país de la lista."

        if len(self.correo) > 150 or not _RE_CORREO.fullmatch(self.correo):
            errores["correo"] = "Ingresa un correo electrónico válido."

        if self.telefono:
            digitos = sum(c.isdigit() for c in self.telefono)
            if not _RE_TELEFONO.fullmatch(self.telefono) or digitos < 7:
                errores["telefono"] = "Revisa el número de teléfono (mínimo 7 dígitos)."

        if not self._areas:
            errores["areas"] = "Selecciona al menos un área de colaboración."
        elif areas_validas is not None and not set(self._areas) <= set(areas_validas):
            errores["areas"] = "Una de las áreas seleccionadas no es válida."

        if self.modalidad not in MODALIDADES:
            errores["modalidad"] = "Selecciona una modalidad válida."

        if self.disponibilidad not in DISPONIBILIDADES:
            errores["disponibilidad"] = "Selecciona tu disponibilidad."

        if len(self.motivacion) > 1000:
            errores["motivacion"] = "La motivación no puede superar los 1000 caracteres."

        if not self.acepta_privacidad:
            errores["privacidad"] = "Debes aceptar la política de privacidad."

        return errores

    def a_diccionario(self):
        """Datos para volver a mostrar el formulario sin que el usuario reescriba todo."""
        return {
            "nombre": self.nombre, "pais": self.pais, "correo": self.correo,
            "telefono": self.telefono, "modalidad": self.modalidad,
            "disponibilidad": self.disponibilidad, "motivacion": self.motivacion,
            "areas": self.areas, "privacidad": self.acepta_privacidad,
        }
