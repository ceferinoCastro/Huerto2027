import {interpretarErrorCampania} from "./campaign-errors.js";
import {API_REQUEST_BASE_URL} from "./configuracion.js?v=4";

const API_V1 = API_REQUEST_BASE_URL + "/api/v1";

export class ApiError extends Error {
  constructor(message,status,fields={}){super(message);this.name="ApiError";this.status=status;this.fields=fields}
}

function errorDetail(data,status){
  if(typeof data?.detail==="string")return data.detail;
  if(Array.isArray(data?.detail))return data.detail.map(item=>item.msg||JSON.stringify(item)).join("; ");
  if(status===502)return "FastAPI no está disponible en http://127.0.0.1:8000";
  if(status===503)return "MongoDB no está disponible";
  if(status===504)return "FastAPI agotó el tiempo de espera";
  return "FastAPI respondió "+status;
}

async function fetchApi(url,options,upload=false){
  try{return await fetch(url,options)}
  catch(error){
    if(error instanceof TypeError){
      throw new ApiError(upload
        ? "La conexión se interrumpió antes de recibir una respuesta. La importación puede haber continuado; revise el resumen antes de reintentar."
        : "No fue posible conectar con FastAPI. Compruebe el backend y la configuración CORS.",0);
    }
    throw error;
  }
}

export async function requestJSON(path,options={}){
  const response=await fetchApi(API_V1+path,{
    ...options,
    headers:{Accept:"application/json","Content-Type":"application/json",...(options.headers||{})},
    cache:"no-store"
  });
  const body=await response.text();
  let data=null;
  try{data=body?JSON.parse(body):null}
  catch(error){throw new ApiError("FastAPI devolvió una respuesta JSON inválida",response.status)}
  if(!response.ok){
    if(path.startsWith("/campanias")){
      const detail=interpretarErrorCampania(data,path.includes("/finalizar")?"finalizar":"guardar");
      console.debug("Error de campañas",response.status,data);
      throw new ApiError(detail.message,response.status,detail.fields);
    }
    throw new ApiError(errorDetail(data,response.status),response.status);
  }
  if(data===null||typeof data!=="object")throw new ApiError("FastAPI devolvió una respuesta JSON inválida",response.status);
  return data;
}

async function requestForm(path,formData){
  const response=await fetchApi(API_V1+path,{method:"POST",headers:{Accept:"application/json"},body:formData,cache:"no-store"},true);
  const data=await response.json().catch(()=>null);
  if(!response.ok)throw new ApiError(errorDetail(data,response.status),response.status);
  return data;
}

export const fetchColegios=()=>requestJSON("/colegios");
export const fetchSensores=()=>requestJSON("/sensores");
export const fetchVariables=()=>requestJSON("/variables");
export const fetchResumenLocalidad=localidad=>requestJSON("/localidades/"+encodeURIComponent(localidad)+"/lecturas/resumen");
export const fetchAsociaciones=localidad=>requestJSON("/asociaciones-sensores?localidad="+encodeURIComponent(localidad));
export const fetchUltimasEducativas=localidad=>requestJSON("/localidades/"+encodeURIComponent(localidad)+"/variables-educativas/ultima");
export const crearAsociacion=payload=>requestJSON("/asociaciones-sensores",{method:"POST",body:JSON.stringify(payload)});
export const actualizarAsociacion=(id,payload)=>requestJSON("/asociaciones-sensores/"+encodeURIComponent(id),{method:"PUT",body:JSON.stringify(payload)});
export const eliminarAsociacion=id=>requestJSON("/asociaciones-sensores/"+encodeURIComponent(id),{method:"DELETE"});
export const guardarMedicionesPlantas=payload=>requestJSON("/mediciones-plantas",{method:"POST",body:JSON.stringify(payload)});
export const fetchMedicionesPlantas=(localidad,fecha,cicloId="general")=>requestJSON("/mediciones-plantas?localidad="+encodeURIComponent(localidad)+"&fecha="+encodeURIComponent(fecha)+"&ciclo_id="+encodeURIComponent(cicloId));
export const fetchPromediosPlantas=(localidad,dias=30)=>requestJSON("/mediciones-plantas/promedio?localidad="+encodeURIComponent(localidad)+"&dias="+encodeURIComponent(dias));
export const analizarCsvHanna=archivo=>{const formData=new FormData();formData.append("archivo",archivo);return requestForm("/mediciones-hanna/analizar-csv",formData)};
export const importarCsvHanna=(archivo,colegioId=null)=>{const formData=new FormData();formData.append("archivo",archivo);if(colegioId)formData.append("colegio_id",colegioId);return requestForm("/mediciones-hanna/importar-csv",formData)};
export const fetchResumenHanna=localidad=>requestJSON("/mediciones-hanna/resumen?localidad="+encodeURIComponent(localidad));
export const fetchDataloggersHanna=()=>requestJSON("/dataloggers-hanna");
export const corregirAsignacionHanna=(serial,colegioId)=>requestJSON("/dataloggers-hanna/"+encodeURIComponent(serial)+"/corregir-asignacion",{method:"PUT",body:JSON.stringify({colegio_id:colegioId,confirmar:true})});
export const reemplazarHanna=(serial,payload)=>requestJSON("/dataloggers-hanna/"+encodeURIComponent(serial)+"/reemplazar",{method:"POST",body:JSON.stringify(payload)});
export const fetchCampanias=colegioId=>requestJSON("/campanias?colegio_id="+encodeURIComponent(colegioId));
export const fetchCampaniaActiva=colegioId=>requestJSON("/campanias/activa?colegio_id="+encodeURIComponent(colegioId));
export const crearCampania=payload=>requestJSON("/campanias",{method:"POST",body:JSON.stringify(payload)});
export const actualizarCampania=(id,payload)=>requestJSON("/campanias/"+encodeURIComponent(id),{method:"PATCH",body:JSON.stringify(payload)});
export const finalizarCampania=(id,payload)=>requestJSON("/campanias/"+encodeURIComponent(id)+"/finalizar",{method:"PUT",body:JSON.stringify(payload)});
export const cancelarCampania=id=>requestJSON("/campanias/"+encodeURIComponent(id)+"/cancelar",{method:"PUT",body:JSON.stringify({confirmar:true})});
