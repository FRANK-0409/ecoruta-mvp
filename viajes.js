const filtros = document.querySelector("#filtros");
const lista = document.querySelector("#publicaciones");
const estado = document.querySelector("#estado-viajes");
const plantilla = document.querySelector("#tarjeta-publicacion");
const publicarDialog = document.querySelector("#publicar-dialog");
const publicar = document.querySelector("#form-publicar");
const publicarError = document.querySelector("#publicar-error");
const publicarContexto = document.querySelector("#publicar-contexto");
const datosAuto = document.querySelector("#datos-auto");
const datosOrigen = document.querySelector("#datos-origen");
const referenciaGrupo = document.querySelector("#referencia-grupo");
const unirseDialog = document.querySelector("#unirse-dialog");
const unirse = document.querySelector("#form-unirse");
const unirseError = document.querySelector("#unirse-error");
const fechaFormato = new Intl.DateTimeFormat("es-PE", {dateStyle: "long", timeZone: "UTC"});
const soles = new Intl.NumberFormat("es-PE", {style: "currency", currency: "PEN"});
let modoPublicacion;
let grupoOferta;
let operacionPublicacion;
let publicacionUnirse;
let consultaActual;
let backendDisponible = false;
let aliasActual = "";

function campo(form, name) {
  return form.elements.namedItem(name);
}

for (const form of [filtros, publicar]) {
  for (const [value, sede] of Object.entries(sedesTecsup)) {
    campo(form, "sede").add(new Option(sede.nombre, value));
  }
}

const sedeSolicitada = new URLSearchParams(location.search).get("sede");
if (Object.hasOwn(sedesTecsup, sedeSolicitada)) campo(filtros, "sede").value = sedeSolicitada;

async function solicitar(path = "", data, signal) {
  const options = data === undefined ? { signal } : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
  const response = await fetch("api/publicaciones" + path, { ...options, cache: "no-store" });
  const json = response.headers.get("content-type")?.includes("application/json");
  if (!json) {
    throw new Error(response.status === 404
      ? "Los viajes compartidos todavía no están disponibles en este sitio."
      : "No se pudo consultar el servicio de viajes. Inténtalo otra vez.");
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

function mensaje(element, value) {
  element.textContent = value;
  element.hidden = !value;
}

function actualizarPlanificador() {
  document.querySelector("#ir-al-planificador").href = "./?sede=" + campo(filtros, "sede").value;
}

function estadoLista(value, error = false) {
  estado.textContent = value;
  estado.classList.toggle("ride-error", error);
}

function errorTexto(error) {
  return error instanceof TypeError ? "No hay conexión con EcoRuta. Intenta de nuevo." : error.message;
}

function boton(text, action, secondary = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = secondary ? "ride-button secondary" : "ride-button";
  button.textContent = text;
  button.addEventListener("click", () => action(button));
  return button;
}

function vacio(text) {
  const empty = document.createElement("p");
  empty.className = "ride-panel ride-empty";
  empty.textContent = text;
  lista.replaceChildren(empty);
}

function editarSeccion(section, enabled) {
  section.hidden = !enabled;
  for (const control of section.querySelectorAll("input, select")) control.disabled = !enabled;
}

function abrirPublicacion(tipo, group = null) {
  if (!backendDisponible) return;
  modoPublicacion = tipo;
  grupoOferta = group;
  operacionPublicacion = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte =>
    byte.toString(16).padStart(2, "0")
  ).join("");
  publicar.reset();
  campo(publicar, "alias").value = aliasActual;
  campo(publicar, "sede").value = group?.sede ?? campo(filtros, "sede").value;
  campo(publicar, "distrito").value = group?.distrito ?? campo(filtros, "distrito").value;
  campo(publicar, "fecha").value = group?.fecha ?? campo(filtros, "fecha").value;
  editarSeccion(datosOrigen, !group);
  editarSeccion(datosAuto, tipo === "viaje");
  editarSeccion(referenciaGrupo, tipo === "grupo");
  document.querySelector("#publicar-titulo").textContent = group ? "Ofrecer asientos al grupo"
    : tipo === "viaje" ? "Ofrecer asientos" : "Buscar compañía";
  document.querySelector("#etiqueta-hora").textContent = tipo === "viaje" ? "Hora de recojo" : "Hora límite de llegada";
  mensaje(publicarContexto, group
    ? group.distrito + " → " + sedesTecsup[group.sede].nombre + " · Llegada hasta las " + group.hora
    : "");
  mensaje(publicarError, "");
  publicarDialog.showModal();
  campo(publicar, "alias").focus();
}

function abrirSolicitud(item) {
  publicacionUnirse = item;
  unirse.reset();
  campo(unirse, "alias").value = aliasActual;
  const ride = item.tipo === "viaje";
  document.querySelector("#unirse-titulo").textContent = ride ? "Solicitar un asiento" : "Unirme al grupo";
  document.querySelector("#unirse-contexto").textContent = ride
    ? "El conductor confirmará tu solicitud si hay cupos disponibles."
    : "Te sumarás a la solicitud de " + item.alias + " desde " + item.distrito + ".";
  document.querySelector("#unirse-enviar").textContent = ride ? "Enviar solicitud" : "Unirme";
  mensaje(unirseError, "");
  unirseDialog.showModal();
  campo(unirse, "alias").focus();
}

async function confirmar(item, solicitud, button) {
  button.disabled = true;
  try {
    await solicitar("/" + item.id + "/confirmar", { solicitud: solicitud.id });
    await cargar("Asiento confirmado.");
  } catch (error) {
    await cargar();
    estadoLista(errorTexto(error), true);
  } finally {
    button.disabled = false;
  }
}

function solicitudes(item, section) {
  if (!item.solicitudes.length) return;
  section.hidden = false;
  const heading = document.createElement("h4");
  heading.textContent = "Solicitudes de asiento";
  section.append(heading);
  for (const solicitud of item.solicitudes) {
    const row = document.createElement("div");
    row.className = "ride-request";
    const name = document.createElement("span");
    name.textContent = solicitud.alias + " · " + (solicitud.estado === "confirmado" ? "Confirmado" : "Pendiente");
    row.append(name);
    if (solicitud.estado === "pendiente" && item.activo && item.disponibles > 0) {
      row.append(boton("Confirmar a " + solicitud.alias, button => confirmar(item, solicitud, button), true));
    }
    section.append(row);
  }
}

function tarjeta(item) {
  const card = plantilla.content.firstElementChild.cloneNode(true);
  card.dataset.id = item.id;
  const fields = Object.fromEntries(
    Array.from(card.querySelectorAll("[data-ride]"), node => [node.dataset.ride, node])
  );
  const ride = item.tipo === "viaje";
  fields.tipo.textContent = ride ? "Asientos ofrecidos" : "Grupo que busca viajar";
  fields.estado.textContent = ride
    ? (item.disponibles === 0 ? "Lleno" : item.disponibles + " de " + item.cupos + " libres")
    : item.integrantes + (item.integrantes === 1 ? " estudiante" : " estudiantes");
  if (ride && item.disponibles === 0) fields.estado.dataset.status = "lleno";
  if (!item.activo) fields.estado.textContent = "Finalizado";
  fields.distrito.textContent = item.distrito;
  fields.sede.textContent = sedesTecsup[item.sede].nombre;
  fields.fecha.textContent = fechaFormato.format(new Date(item.fecha + "T12:00:00Z"));
  fields["etiqueta-hora"].textContent = ride ? "Recojo" : "Llegar antes de";
  fields.hora.textContent = item.hora;
  fields.aporte.hidden = !ride;
  if (ride) fields.dato.textContent = soles.format(item.aporte / 100);
  fields.autor.textContent = (ride ? "Conduce " : "Publicó ") + item.alias + (item.propia ? " · Tú" : "");
  if (item.grupo_alias) fields.autor.textContent += " · Oferta al grupo de " + item.grupo_alias;
  if (ride) {
    mensaje(fields.punto, item.punto + " · Llegada estimada " + item.llegada);
    if (item.propia) {
      solicitudes(item, fields.solicitudes);
    } else if (item.mi_estado) {
      const status = document.createElement("span");
      status.className = "ride-badge";
      status.textContent = item.mi_estado === "confirmado" ? "Asiento confirmado"
        : item.disponibles === 0 ? "Solicitud pendiente · viaje lleno" : "Solicitud enviada";
      fields.acciones.append(status);
    } else if (item.activo && item.puede_solicitar && item.disponibles > 0) {
      fields.acciones.append(boton("Solicitar asiento", () => abrirSolicitud(item)));
    }
  } else {
    if (item.punto) mensaje(fields.punto, "Sale desde " + item.punto);
    if (item.activo && !item.propia && !item.mi_estado) {
      fields.acciones.append(boton("Unirme al grupo", () => abrirSolicitud(item)));
      fields.acciones.append(boton("Ofrecer asientos", () => abrirPublicacion("viaje", item), true));
    }
    if (item.mi_estado) {
      const badge = document.createElement("span");
      badge.className = "ride-badge";
      badge.textContent = "Estás en el grupo";
      fields.acciones.append(badge);
    }
  }
  return card;
}

function accionesDisponibles(enabled) {
  backendDisponible = enabled;
  document.querySelector("#ofrecer-viaje").disabled = !enabled;
  document.querySelector("#buscar-grupo").disabled = !enabled;
}

async function cargar(notice = "") {
  consultaActual?.abort();
  const request = new AbortController();
  consultaActual = request;
  const query = new URLSearchParams(new FormData(filtros));
  actualizarPlanificador();
  lista.setAttribute("aria-busy", "true");
  estadoLista("Cargando publicaciones…");
  try {
    const result = await solicitar("?" + query, undefined, request.signal);
    if (request !== consultaActual) return;
    const items = result.publicaciones;
    campo(publicar, "fecha").min = result.hoy;
    accionesDisponibles(true);
    if (items.length) {
      lista.replaceChildren(...items.map(tarjeta));
    } else {
      vacio("Todavía no hay publicaciones para esta búsqueda. Prueba otro distrito o publica un viaje.");
    }
    const count = items.length + (items.length === 1 ? " publicación" : " publicaciones");
    estadoLista(notice ? notice + " " + count : count);
  } catch (error) {
    if (request !== consultaActual) return;
    accionesDisponibles(false);
    vacio("No se pudieron cargar las publicaciones.");
    estadoLista(errorTexto(error), true);
  } finally {
    if (request === consultaActual) lista.setAttribute("aria-busy", "false");
  }
}

function mostrarPublicacion(data, tipo) {
  campo(filtros, "sede").value = data.sede;
  campo(filtros, "distrito").value = data.distrito;
  campo(filtros, "fecha").value = data.fecha;
  campo(filtros, "tipo").value = tipo;
}

publicar.addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.submitter;
  const group = grupoOferta;
  const data = Object.fromEntries(new FormData(publicar));
  data.tipo = modoPublicacion;
  data.operacion = operacionPublicacion;
  if (data.tipo === "viaje") {
    data.cupos = Number(data.cupos);
    data.aporte = Math.round(Number(data.aporte) * 100);
  } else {
    data.punto = data["punto-grupo"];
    delete data["punto-grupo"];
  }
  mensaje(publicarError, "");
  button.disabled = true;
  try {
    await solicitar(group ? "/" + group.id + "/ofrecer" : "", data);
    aliasActual = data.alias;
    publicarDialog.close();
    mostrarPublicacion(group ?? data, group ? "" : data.tipo);
    await cargar(group ? "Oferta enviada al grupo." : "Publicación creada.");
  } catch (error) {
    mensaje(publicarError, errorTexto(error));
  } finally {
    button.disabled = false;
  }
});

unirse.addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.submitter;
  const item = publicacionUnirse;
  const data = Object.fromEntries(new FormData(unirse));
  mensaje(unirseError, "");
  button.disabled = true;
  try {
    await solicitar("/" + item.id + "/unirse", data);
    aliasActual = data.alias;
    unirseDialog.close();
    await cargar(item.tipo === "viaje" ? "Solicitud enviada al conductor." : "Te uniste al grupo.");
  } catch (error) {
    mensaje(unirseError, errorTexto(error));
  } finally {
    button.disabled = false;
  }
});

for (const [dialog, button] of [
  [publicarDialog, document.querySelector("#cerrar-publicar")],
  [unirseDialog, document.querySelector("#cerrar-unirse")],
]) {
  button.addEventListener("click", () => dialog.close());
}

filtros.addEventListener("submit", event => {
  event.preventDefault();
  cargar();
});
campo(filtros, "sede").addEventListener("change", () => {
  campo(filtros, "distrito").value = "";
  cargar();
});
document.querySelector("#ofrecer-viaje").addEventListener("click", () => abrirPublicacion("viaje"));
document.querySelector("#buscar-grupo").addEventListener("click", () => abrirPublicacion("grupo"));
accionesDisponibles(false);
cargar();
