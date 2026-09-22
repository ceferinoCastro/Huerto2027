export const SENSOR_GROUP_CATALOG = Object.freeze([
  { key: "air", label: "Aire", accent: "#2389bd" },
  { key: "plant", label: "Planta", accent: "#85d357" },
  { key: "earth", label: "Tierra y raíces", accent: "#b9653a" },
  { key: "water", label: "Agua del estanque", accent: "#217408e3" },
]);

export const BACKGROUND_CROP = Object.freeze({
  originalHeight: 1327,
  topPixels: 265,
  bottomPixels: 66,
  visibleHeight: 996,
  topPercent: 20,
  visiblePercent: 75,
});

const MOBILE_ORDER_BY_GROUP = {
  air: { temperatura_aire: 1, humedad_aire: 2 },
  plant: { humedad_hojas: 1, altura_planta: 2 },
  earth: { temperatura_tierra: 1, temperatura_bajo_tierra: 2, largo_raiz: 3, humedad_tierra: 4 },
  water: { ph_agua: 1, sales_agua: 2, temperatura_agua: 3 },
};

function cartelEsVisible(cartel) {
  return cartel.visible_frontend !== false && cartel.posicion_x != null && cartel.destino_x != null;
}

function mapearCartelVisual(cartel) {
  const ruta = [];
  if (cartel.ruta_punto1_x != null && cartel.ruta_punto1_y != null) {
    ruta.push({ x: cartel.ruta_punto1_x, y: cartel.ruta_punto1_y });
  }
  if (cartel.ruta_punto2_x != null && cartel.ruta_punto2_y != null) {
    ruta.push({ x: cartel.ruta_punto2_x, y: cartel.ruta_punto2_y });
  }
  return {
    key: cartel.clave_educativa,
    label: cartel.nombre_educativo,
    explanation: cartel.explicacion || "",
    shortLabel: cartel.etiqueta_corta || cartel.nombre_educativo,
    icon: cartel.icono,
    unit: cartel.unidad,
    source: cartel.fuente_sugerida,
    group: cartel.grupo_visual,
    sharedTarget: cartel.compartir_conexion_con || null,
    showConnection: cartel.mostrar_conexion !== false,
    position: {
      desktop: { x: cartel.posicion_x, y: cartel.posicion_y },
      mobile: { order: MOBILE_ORDER_BY_GROUP[cartel.grupo_visual]?.[cartel.clave_educativa] || 1 },
    },
    target: { x: cartel.destino_x, y: cartel.destino_y, zone: cartel.destino_zona || "" },
    route: ruta,
    anchor: cartel.ancla || "bottom",
    ...(cartel.regla ? { ruler: cartel.regla } : {}),
  };
}

export async function cargarCatalogoVisual() {
  const response = await fetch("/api/v1/carteles");
  if (!response.ok) throw new Error("No fue posible cargar el catálogo de carteles");
  const data = await response.json();
  const items = Array.isArray(data.items) ? data.items : [];
  return items.filter(cartelEsVisible).map(mapearCartelVisual);
}
