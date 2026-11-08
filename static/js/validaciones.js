/* Validaciones en el navegador: mejoran la experiencia del usuario.
   La validación que realmente protege los datos es la de Python y la de SQL Server,
   porque cualquiera podría enviar datos sin ejecutar este archivo. */
document.addEventListener("DOMContentLoaded", () => {
  const formulario = document.getElementById("formRegistro");
  if (!formulario) return;

  const RE_NOMBRE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .\-]+$/;
  const RE_CORREO = /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$/;
  const RE_TELEFONO = /^\+?[0-9\s()\-]{7,30}$/;

  const $ = (id) => document.getElementById(id);
  const campos = {
    nombre: $("nombre"), pais: $("pais"), correo: $("correo"), telefono: $("telefono"),
    modalidad: $("modalidad"), disponibilidad: $("disponibilidad"),
    motivacion: $("motivacion"), privacidad: $("privacidad"),
  };

  // Cada regla devuelve un mensaje de error o "" si el campo es correcto
  const reglas = {
    nombre: (v) => {
      v = v.trim().replace(/\s+/g, " ");
      if (v.length < 5 || v.length > 150) return "Ingresa tu nombre completo (entre 5 y 150 caracteres).";
      if (!RE_NOMBRE.test(v)) return "El nombre solo puede contener letras, espacios, guiones y apóstrofes.";
      return "";
    },
    pais: (v) => (v ? "" : "Selecciona un país de la lista."),
    correo: (v) => (RE_CORREO.test(v.trim()) && v.trim().length <= 150 ? "" : "Ingresa un correo electrónico válido."),
    telefono: (v) => {
      v = v.trim();
      if (!v) return "";
      const digitos = (v.match(/[0-9]/g) || []).length;
      return RE_TELEFONO.test(v) && digitos >= 7 ? "" : "Revisa el número de teléfono (mínimo 7 dígitos).";
    },
    modalidad: (v) => (v ? "" : "Selecciona una modalidad válida."),
    disponibilidad: (v) => (v ? "" : "Selecciona tu disponibilidad."),
    motivacion: (v) => (v.length <= 1000 ? "" : "La motivación no puede superar los 1000 caracteres."),
  };

  function mostrarError(nombre, mensaje, elemento) {
    const zona = $("error-" + nombre);
    if (zona) zona.textContent = mensaje;
    if (elemento) {
      elemento.classList.toggle("is-invalid", Boolean(mensaje));
      elemento.classList.toggle("is-valid", !mensaje && elemento.value.trim() !== "");
      elemento.setAttribute("aria-invalid", mensaje ? "true" : "false");
    }
  }

  function validarCampo(nombre) {
    const elemento = campos[nombre];
    let mensaje = "";
    if (nombre === "privacidad") {
      mensaje = elemento.checked ? "" : "Debes aceptar la política de privacidad.";
      mostrarError(nombre, mensaje, null);
    } else {
      mensaje = reglas[nombre](elemento.value);
      mostrarError(nombre, mensaje, elemento);
    }
    return mensaje === "";
  }

  function validarAreas() {
    const marcadas = formulario.querySelectorAll('input[name="areas"]:checked').length;
    const mensaje = marcadas > 0 ? "" : "Selecciona al menos un área de colaboración.";
    mostrarError("areas", mensaje, null);
    return mensaje === "";
  }

  // Validar al salir de cada campo y limpiar el error mientras se corrige
  Object.keys(reglas).forEach((nombre) => {
    campos[nombre].addEventListener("blur", () => validarCampo(nombre));
    campos[nombre].addEventListener("input", () => {
      if (campos[nombre].classList.contains("is-invalid")) validarCampo(nombre);
    });
    campos[nombre].addEventListener("change", () => validarCampo(nombre));
  });
  campos.privacidad.addEventListener("change", () => validarCampo("privacidad"));
  formulario.querySelectorAll('input[name="areas"]').forEach((c) => c.addEventListener("change", validarAreas));

  // Contador de caracteres de la motivación
  const contador = $("contadorMotivacion");
  const actualizarContador = () => { contador.textContent = campos.motivacion.value.length; };
  campos.motivacion.addEventListener("input", actualizarContador);
  actualizarContador();

  // Envío
  const boton = $("btnEnviar");
  const textoBoton = boton.textContent;
  formulario.addEventListener("submit", (evento) => {
    const resultados = Object.keys(campos).map((n) => [n, validarCampo(n)]);
    const areasOk = validarAreas();
    const primerError = resultados.find(([, ok]) => !ok);

    if (primerError || !areasOk) {
      evento.preventDefault();
      const destino = primerError ? campos[primerError[0]] : $("grupoAreas");
      destino.scrollIntoView({ behavior: "smooth", block: "center" });
      if (primerError) destino.focus({ preventScroll: true });
      return;
    }
    // Evitar envíos dobles
    boton.disabled = true;
    boton.textContent = "Enviando...";
  });

  // Si el usuario vuelve atrás con el navegador, reactivar el botón
  window.addEventListener("pageshow", () => {
    boton.disabled = false;
    boton.textContent = textoBoton;
  });
});
