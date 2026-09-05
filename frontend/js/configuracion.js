export const API_BASE_URL = "http://127.0.0.1:8000";
export const USAR_API = true;

// En desarrollo, servidor.py reenvía /api para evitar el bloqueo CORS entre
// los puertos 5500 y 8000 sin modificar FastAPI.
const ES_SERVIDOR_LOCAL = typeof window !== "undefined" &&
 ["localhost","127.0.0.1"].includes(window.location.hostname) &&
 window.location.port === "5500";
const API_REQUEST_BASE_URL = ES_SERVIDOR_LOCAL ? window.location.origin : API_BASE_URL;
const API_V1 = API_REQUEST_BASE_URL + "/api/v1";

export const ENDPOINT_RESUMEN = localidad =>
 API_V1 + "/localidades/" + encodeURIComponent(localidad) + "/lecturas/resumen";

export const ENDPOINT_HISTORIAL = (localidad,variable,horas,puntos=60) => {
 const url=new URL(API_V1 + "/localidades/" + encodeURIComponent(localidad) + "/lecturas/historial");
 url.search=new URLSearchParams({variable,horas:String(horas),puntos:String(puntos)});
 return url.toString();
};

export const ENDPOINT_PROMEDIO_PLANTAS = (localidad,dias=30) => {
 const url=new URL(API_V1 + "/mediciones-plantas/promedio");
 url.search=new URLSearchParams({localidad,dias:String(dias)});
 return url.toString();
};

export const ENDPOINT_SERIE_HANNA = (localidad,variable="temperatura",dias=7) => {
 const url=new URL(API_V1 + "/mediciones-hanna/series");
 url.search=new URLSearchParams({localidad,variable,dias:String(dias)});
 return url.toString();
};

export const ENDPOINT_ULTIMA_HANNA = (localidad,variable="temperatura") => {
 const url=new URL(API_V1 + "/mediciones-hanna/ultima");
 url.search=new URLSearchParams({localidad,variable});
 return url.toString();
};

export const ENDPOINT_ULTIMAS_EDUCATIVAS = localidad =>
 API_V1 + "/localidades/" + encodeURIComponent(localidad) + "/variables-educativas/ultima";

export const ENDPOINT_HISTORIAL_EDUCATIVO = (localidad,variable,horas,puntos=60,campaniaId=null) => {
 const url=new URL(API_V1 + "/localidades/" + encodeURIComponent(localidad) + "/variables-educativas/" + encodeURIComponent(variable) + "/historial");
 const parametros={horas:String(horas),puntos:String(puntos)};
 if(campaniaId)parametros.campania_id=campaniaId;
 url.search=new URLSearchParams(parametros);
 return url.toString();
};
