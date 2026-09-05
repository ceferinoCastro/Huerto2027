const labels = {
  nombre: "el nombre de la campaña", cultivo: "el cultivo",
  fecha_siembra: "la fecha de siembra", fecha_cosecha_estimada: "la cosecha estimada",
  fecha_cosecha_real: "la fecha real de término", resultado_final: "un resumen de la campaña",
  observaciones: "las observaciones", observaciones_finales: "las observaciones finales",
  confirmar: "la confirmación explícita", revision: "la revisión de la campaña",
};

export function interpretarErrorCampania(data, action = "guardar") {
  const fallback = `No fue posible ${action} la campaña. Revise los datos e inténtelo nuevamente.`;
  const fields = {};
  if (Array.isArray(data?.detail)) {
    for (const item of data.detail) {
      const field = item.loc?.find(part => Object.hasOwn(labels, part));
      if (!field) continue;
      fields[field] = item.type === "missing"
        ? (field === "resultado_final" ? "Debe escribir un resumen de la campaña."
          : field === "confirmar" ? "Debe confirmar explícitamente la finalización."
          : `Debe indicar ${labels[field]}.`)
        : `Revise ${labels[field]}: el valor no es válido.`;
    }
    return {message: Object.values(fields).join(" ") || fallback, fields};
  }
  // Domain errors are deliberately written in Spanish by the campaign service.
  if (typeof data?.detail === "string" && /^(La |El |Debe |Solo |Campaña |MongoDB )/.test(data.detail)) {
    return {message: data.detail, fields};
  }
  return {message: fallback, fields};
}
