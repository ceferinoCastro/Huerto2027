import {ENDPOINT_HISTORIAL_EDUCATIVO,ENDPOINT_ULTIMAS_EDUCATIVAS,USAR_API} from "./configuracion.js?v=7";

async function solicitarJSON(url){
 const response=await fetch(url,{headers:{Accept:"application/json"},cache:"no-store"});
 if(!response.ok)throw new Error("FastAPI respondió "+response.status);
 return response.json();
}

export async function fetchUltimasEducativas(localidad){
 if(!USAR_API)return null;
 return solicitarJSON(ENDPOINT_ULTIMAS_EDUCATIVAS(localidad));
}

export async function fetchHistorialEducativo(localidad,variable,horas=24,puntos=60,campaniaId=null){
 if(!USAR_API)return null;
 return solicitarJSON(ENDPOINT_HISTORIAL_EDUCATIVO(localidad,variable,horas,puntos,campaniaId));
}
