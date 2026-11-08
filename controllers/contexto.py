"""Datos que necesita la vista del formulario de colaboradores (público y admin)."""
from models.colaborador import DISPONIBILIDADES, MODALIDADES, PAISES


def contexto_formulario(areas, datos=None, errores=None):
    """Diccionario con las listas de opciones y los datos a mostrar en el formulario."""
    return {
        "areas": areas,
        "paises": PAISES,
        "modalidades": MODALIDADES,
        "disponibilidades": DISPONIBILIDADES,
        "datos": datos or {"areas": []},
        "errores": errores or {},
    }
