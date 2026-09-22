const ESTADOS_SIN_DATOS = new Set([
  "sin_asociacion",
  "sin_datos",
  "sin_equipo_hanna",
  "sin_datos_validos",
]);

const FORMATO_NUMERO = new Intl.NumberFormat("es-CL", {
  maximumFractionDigits: 4,
});

const FORMATO_FECHA = new Intl.DateTimeFormat("es-CL", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "America/Santiago",
});

const FORMATO_FECHA_LOCAL = new Intl.DateTimeFormat("es-CL", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

function fechaValida(valor) {
  return valor instanceof Date && Number.isFinite(valor.getTime());
}

export function formatearFechaMedicion(valor) {
  if (typeof valor !== "string" || !valor.trim()) return "";
  const texto = valor.trim();
  const fechaLocal = texto.match(
    /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?$/,
  );
  if (fechaLocal) {
    const [, anio, mes, dia, hora = "00", minuto = "00"] = fechaLocal;
    const fecha = new Date(Date.UTC(+anio, +mes - 1, +dia, +hora, +minuto));
    const coincide = fechaValida(fecha)
      && fecha.getUTCFullYear() === +anio
      && fecha.getUTCMonth() === +mes - 1
      && fecha.getUTCDate() === +dia
      && fecha.getUTCHours() === +hora
      && fecha.getUTCMinutes() === +minuto;
    return coincide ? FORMATO_FECHA_LOCAL.format(fecha) : "";
  }
  const fecha = new Date(texto.replace(" ", "T"));
  return fechaValida(fecha) ? FORMATO_FECHA.format(fecha) : "";
}

export function estadoCartel(lectura, cartel) {
  const base = {
    value: null,
    formattedValue: "",
    unit: "",
    datetime: null,
    source: lectura?.fuente || cartel.source,
    is_stale: null,
  };
  if (lectura?.estado === "cargando") {
    return { ...base, status: "loading", text: "Cargando…", updatedText: "" };
  }
  if (lectura?.estado === "ok" && lectura.valor !== null && lectura.valor !== "") {
    let value = Number(lectura.valor);
    if (Number.isFinite(value)) {
      let unit = typeof lectura.unidad === "string" ? lectura.unidad.trim() : "";
      if (cartel.key === "humedad_tierra" && (unit === "m³/m³" || unit === "m3/m3" || !unit || value <= 1)) {
        value *= 100;
        unit = "%";
      }
      const datetime = typeof lectura.datetime_local === "string" ? lectura.datetime_local : null;
      const formattedDate = formatearFechaMedicion(datetime);
      return {
        ...base,
        status: "available",
        value,
        formattedValue: FORMATO_NUMERO.format(value),
        unit,
        datetime,
        text: `${FORMATO_NUMERO.format(value)}${unit ? ` ${unit}` : ""}`,
        updatedText: formattedDate ? `Actualizado: ${formattedDate}` : "",
      };
    }
  }
  if (!lectura || ESTADOS_SIN_DATOS.has(lectura.estado)) {
    return { ...base, status: "no_data", text: "Sin datos", updatedText: "" };
  }
  return { ...base, status: "error", text: "Sin conexión", updatedText: "" };
}
