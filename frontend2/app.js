import {ApiError,actualizarCampania,actualizarAsociacion,analizarCsvHanna,cancelarCampania,corregirAsignacionHanna,crearAsociacion,crearCampania,eliminarAsociacion,fetchAsociaciones,fetchCampanias,fetchCampaniaActiva,fetchColegios,fetchDataloggersHanna,fetchMedicionesPlantas,fetchPromediosPlantas,fetchResumenLocalidad,fetchSensores,fetchUltimasEducativas,fetchVariables,finalizarCampania,guardarMedicionesPlantas,importarCsvHanna,reemplazarHanna} from "./api.js?v=5";

const localidades={colchane:"Colchane",camina:"Camiña",huara:"Huara","la-tirana":"La Tirana",pica:"Pica",huayquique:"Huayquique"};
const pistasColegio={colchane:"colchane",camina:"camina",huara:"huara","la-tirana":"tirana",pica:"pica",huayquique:"huayquique"};
const state={localidad:"pica",colegios:[],sensoresCatalogo:[],variablesCatalogo:[],resumen:null,sensores:[],variables:[],asociaciones:[],apiAsociacionesDisponible:null,cargandoAsociaciones:false,asociacionesVacias:false,errorConsultaAsociaciones:null,errorOperacionAsociacion:null,editando:null,carga:0,cargandoConfiguracion:true};
const plantState={localidad:"pica",promedios:[],mediciones:[],carga:0,cargaDia:0};
const hannaState={archivo:null,preview:null,equipos:[],carga:0};
const campaignState={colegioId:"",activa:null,items:[],formOpen:false,mode:"create",editing:null,finishing:null,busy:false,carga:0};
const posterState={items:[],catalogo:[],carga:0,cargando:false,error:null};
const $=selector=>document.querySelector(selector);
const normalizar=texto=>(texto||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const escapar=texto=>String(texto??"").replace(/[&<>'"]/g,caracter=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[caracter]);

function definicionCartel(variable){return posterState.catalogo.find(item=>item.clave_educativa===variable)||null}
function iconoCartel(variable){const categoria=definicionCartel(variable)?.categoria;return ({temperatura:"🌡️",humedad:"💧",agua:"🧪",plantas:"🌿"})[categoria]||"●"}
function itemsCargaCarteles(){return posterState.catalogo.map(item=>({variable:item.clave_educativa,nombre:item.nombre_educativo,valor:null,unidad:item.unidad,datetime_local:null,fuente:item.fuente,estado:"cargando",mensaje:"Cargando...",detalle_tecnico:{clave_educativa:item.clave_educativa}}))}
function fechaCartel(valor){
 if(!valor)return "Fecha no disponible";
 const texto=String(valor),soloFecha=/^\d{4}-\d{2}-\d{2}$/.test(texto),fecha=new Date(soloFecha?texto+"T12:00:00":texto);
 if(Number.isNaN(fecha.getTime()))return texto;
 return fecha.toLocaleString("es-CL",soloFecha?{day:"2-digit",month:"2-digit",year:"numeric"}:{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"});
}
function fuenteCartel(fuente){return ({zentra:"Zentra",hanna:"Hanna",manual:"Manual"})[fuente]||"No informada"}
function textoEstadoCartel(item){
 if(item.estado==="cargando")return "Cargando...";
 if(item.estado==="ok")return "Dato real";
 if(item.mensaje)return item.mensaje;
 return ({sin_asociacion:"Variable sin sensor asociado",sin_datos:"Sensor asociado, pero sin mediciones",no_disponible:"No fue posible consultar esta medición"})[item.estado]||"No fue posible consultar esta medición";
}
function detalleCartel(item){
 const detail=item.detalle_tecnico||{},fields=[["Clave educativa",detail.clave_educativa||item.variable],["Colegio ID",detail.colegio_id||item.colegio_id],["Fuente",detail.fuente||item.fuente],["Colección",detail.coleccion],["Datalogger",detail.device_sn],["Sensor",detail.sensor_sn],["Serial Hanna",detail.serial_hanna],["Modelo",detail.modelo||detail.sensor_modelo],["Instrument ID",detail.instrument_id],["Variable técnica",detail.variable_tecnica],["Campo consultado",detail.campo_consultado],["Unidad original",detail.unidad_original],["Fecha original",detail.fecha_original],["Estado asociación",detail.estado_asociacion],["Estado",detail.estado||item.estado]];
 return '<details class="poster-technical"><summary>Ver detalle técnico</summary><dl>'+fields.map(([label,value])=>'<div><dt>'+escapar(label)+'</dt><dd>'+escapar(value??"No informado")+'</dd></div>').join("")+'</dl></details>';
}
function cartelDiagnostico(item){
 const real=item.estado==="ok"&&Number.isFinite(Number(item.valor)),value=real?Number(item.valor).toLocaleString("es-CL",{maximumFractionDigits:4})+(item.unidad?" "+item.unidad:""):textoEstadoCartel(item),stateClass=item.estado==="ok"?"ok":item.estado==="cargando"?"loading":item.estado==="no_disponible"?"error":"empty";
 return '<article class="poster-card '+stateClass+'" data-poster-variable="'+escapar(item.variable)+'"><div class="poster-card-title"><span aria-hidden="true">'+iconoCartel(item.variable)+'</span><h3>'+escapar(item.nombre||item.variable)+'</h3></div><strong class="poster-card-value">'+escapar(value)+'</strong><time>'+escapar(real?fechaCartel(item.datetime_local):"Fecha no disponible")+'</time><span class="poster-card-source">Fuente: '+escapar(fuenteCartel(item.fuente))+'</span><span class="poster-card-state">'+escapar(textoEstadoCartel(item))+'</span>'+detalleCartel(item)+'</article>';
}
function renderVisorCarteles(){
 const items=posterState.items.length?posterState.items:itemsCargaCarteles();
 $("#poster-preview-grid").innerHTML=items.map(cartelDiagnostico).join("");
 const summary=$("#poster-preview-summary");
 if(posterState.cargando){summary.className="poster-preview-summary loading";summary.textContent="Cargando...";return}
 if(posterState.error){summary.className="poster-preview-summary error";summary.textContent="No fue posible consultar los carteles: "+posterState.error;return}
 const counts={ok:0,sin_asociacion:0,sin_datos:0,no_disponible:0};items.forEach(item=>{const estado=item.estado==="sin_equipo_hanna"?"sin_asociacion":item.estado==="sin_datos_validos"?"sin_datos":item.estado;counts[estado]=(counts[estado]||0)+1});
 summary.className="poster-preview-summary "+(counts.no_disponible?"error":"success");summary.textContent=counts.ok+" con datos · "+counts.sin_asociacion+" sin asociación · "+counts.sin_datos+" sin mediciones · "+counts.no_disponible+" no disponibles";
}
async function cargarVisorCarteles(forzar=false){
 if(posterState.cargando&&!forzar)return;
 const carga=++posterState.carga,localidad=state.localidad;posterState.cargando=true;posterState.error=null;posterState.items=itemsCargaCarteles();$("#test-associations").disabled=true;renderVisorCarteles();
 try{const data=await fetchUltimasEducativas(localidad);if(carga!==posterState.carga||localidad!==state.localidad)return;posterState.catalogo=data.catalogo||[];posterState.items=data.items||[]}
 catch(error){if(carga!==posterState.carga||localidad!==state.localidad)return;posterState.error=error.message;posterState.items=itemsCargaCarteles().map(item=>({...item,estado:"no_disponible",mensaje:"No fue posible consultar esta medición",detalle_tecnico:{...item.detalle_tecnico,error:error.message}}))}
 finally{if(carga===posterState.carga&&localidad===state.localidad){posterState.cargando=false;$("#test-associations").disabled=false;renderVisorCarteles();renderAsociaciones()}}
}

function setStatus(tipo,mensaje){const el=$("#status");el.className="status "+tipo;el.textContent=mensaje}
function colegioPorLocalidad(localidad){const pista=pistasColegio[localidad];return state.colegios.find(item=>normalizar(item.nombre).includes(pista)||normalizar(item.comuna)===pista)||null}
function colegioActual(){return colegioPorLocalidad(state.localidad)}
function agruparResumen(items){
 const mapa=new Map();
 items.forEach(item=>{if(!item.sensor_sn)return;const sensor=mapa.get(item.sensor_sn)||{sensor_sn:item.sensor_sn,sensor_name:item.sensor_name||"Sensor sin nombre",port_number:item.port_number,variables:[]};if(item.variable&&!sensor.variables.some(v=>v.nombre===item.variable))sensor.variables.push({nombre:item.variable,unidad:item.units||""});mapa.set(item.sensor_sn,sensor)});
 return [...mapa.values()];
}
function ubicacionSensor(sensorSn){return state.sensoresCatalogo.find(item=>item.sensor_sn===sensorSn)?.ubicacion_fisica||""}
function renderContexto(){
 const colegio=colegioActual(),device=state.resumen?.device_sn||"Sin datalogger asociado";
 $("#colegio").textContent=colegio?.nombre||"Colegio no identificado";$("#localidad-nombre").textContent=localidades[state.localidad];$("#device-sn").textContent=device;
 $("#sensor-count").textContent=state.sensores.length;$("#sensor-summary").textContent=state.sensores.length?state.sensores.map(s=>s.sensor_name).filter((v,i,a)=>a.indexOf(v)===i).join(", "):"Sin sensores detectados";
 $("#variable-count").textContent=state.variables.length;$("#variable-summary").textContent=state.variables.length?state.variables.slice(0,3).map(v=>v.nombre).join(", ")+(state.variables.length>3?"…":""):"Sin variables disponibles";
}
function renderSensores(){
 $("#detected-sensors").innerHTML=state.sensores.length?state.sensores.map(sensor=>'<article class="sensor-item"><strong>'+escapar(sensor.sensor_name)+' · Puerto '+escapar(sensor.port_number??"—")+'</strong><span><code>'+escapar(sensor.sensor_sn)+'</code></span><span>'+(escapar(ubicacionSensor(sensor.sensor_sn))||"Ubicación no registrada")+'</span><div class="sensor-tags">'+sensor.variables.map(v=>'<em>'+escapar(v.nombre)+'</em>').join("")+'</div></article>').join(""):'<p class="empty">No hay sensores detectados para esta localidad.</p>';
}
function opcionesFormulario(){
 const sensorSelect=$("#sensor-sn"),seleccion=sensorSelect.value;
 sensorSelect.innerHTML='<option value="">Selecciona un sensor</option>'+state.sensores.map(s=>'<option value="'+escapar(s.sensor_sn)+'">'+escapar(s.sensor_name)+' · '+escapar(s.sensor_sn)+'</option>').join("");
 sensorSelect.value=seleccion;
 actualizarVariablesFormulario();
}
function actualizarVariablesFormulario(){
 const sensor=state.sensores.find(item=>item.sensor_sn===$("#sensor-sn").value),actual=$("#variable-tecnica").value,variables=sensor?.variables||state.variables;
 $("#variable-tecnica").innerHTML='<option value="">Selecciona una variable</option>'+variables.map(v=>'<option value="'+escapar(v.nombre)+'">'+escapar(v.nombre)+'</option>').join("");
 if(variables.some(v=>v.nombre===actual))$("#variable-tecnica").value=actual;
 if(sensor&&!$("#ubicacion").value)$("#ubicacion").value=ubicacionSensor(sensor.sensor_sn);
 actualizarUnidad();
}
function actualizarUnidad(){
 const nombre=$("#variable-tecnica").value,local=state.variables.find(v=>v.nombre===nombre),catalogo=state.variablesCatalogo.find(v=>v.nombre_ing===nombre);
 if(nombre)$("#unidad").value=local?.unidad||catalogo?.unidad||"";
}
function renderAsociaciones(){
 const apiDisponible=state.apiAsociacionesDisponible===true,notice=$("#endpoint-notice");notice.hidden=state.apiAsociacionesDisponible!==false;$("#endpoint-notice-detail").textContent=state.errorConsultaAsociaciones||"No se pudo conectar con FastAPI.";$("#retry-associations").disabled=state.cargandoAsociaciones;$("#save-button").disabled=!apiDisponible||!state.sensores.length;$("#save-help").textContent=apiDisponible?(state.asociacionesVacias?"API disponible · Sin asociaciones Zentra para este colegio":"Los cambios se guardarán mediante FastAPI."):state.cargandoAsociaciones?"Consultando la API de asociaciones…":"Guardado deshabilitado mientras no sea posible consultar las asociaciones Zentra.";
 if(state.cargandoConfiguracion||posterState.cargando){$("#association-count").textContent="Cargando catálogo…";$("#associations-body").innerHTML='<tr><td colspan="8" class="empty-cell">Cargando configuración de carteles…</td></tr>';return}
 if(!posterState.catalogo.length){$("#association-count").textContent="Catálogo no disponible";$("#associations-body").innerHTML='<tr><td colspan="8" class="empty-cell">No fue posible consultar el catálogo educativo.</td></tr>';return}
 const measurementByKey=new Map(posterState.items.map(item=>[item.variable,item])),associationByKey=new Map(state.asociaciones.filter(item=>(item.source||"zentra")==="zentra").map(item=>[item.clave_educativa,item]));
 const rows=posterState.catalogo.map(definition=>{
  const key=definition.clave_educativa,source=definition.fuente,measurement=measurementByKey.get(key)||{},association=associationByKey.get(key),detail=measurement.detalle_tecnico||{};let origin="—",technical=definition.variable_tecnica,status="Pendiente de asociar",statusClass="pending",visible="—",actions="",configured=false,pending=false,noData=false;
  if(source==="zentra"){
   const disabled=apiDisponible?"":" disabled";
   const sensor=association&&state.sensoresCatalogo.find(item=>item.sensor_sn===association.sensor_sn),associationId=association&&(association._id||association.id),validAssociation=association&&["asociada","provisional"].includes(association.estado_asociacion||"asociada");
   if(association){origin='<strong>'+escapar(sensor?.nombre||sensor?.sensor_name||association.sensor_name||"Sensor")+'</strong><small>'+escapar(association.sensor_sn||"—")+'</small>';technical=association.variable_tecnica||technical;visible=association.visible_frontend===false?"No":"Sí";if(!validAssociation||!association.sensor_sn||!sensor){status="Asociación incompleta";statusClass="incomplete";pending=true}else if(measurement.estado==="sin_datos"){status="Asociado, sin datos";statusClass="no-data";configured=true;noData=true}else{status="Asociado";statusClass="associated";configured=true}actions='<button type="button" data-edit="'+escapar(associationId)+'"'+disabled+'>Editar</button><button type="button" class="delete" data-delete="'+escapar(associationId)+'"'+disabled+'>Eliminar asociación</button>'}
   else{pending=true;actions='<button type="button" data-associate="'+escapar(key)+'"'+disabled+'>Asociar</button>'}
  }else if(source==="hanna"){
   const hasEquipment=measurement.estado!=="sin_equipo_hanna"&&Boolean(detail.serial_hanna);origin=hasEquipment?'<strong>Hanna '+escapar(detail.modelo||detail.sensor_modelo||"HI981420")+'</strong><small>'+escapar(detail.serial_hanna)+'</small>':"—";technical=detail.campo_consultado||definition.variable_tecnica;visible="Sí";if(!hasEquipment){status="Sin equipo Hanna";statusClass="pending";pending=true}else if(measurement.estado==="ok"){status="Disponible";statusClass="available";configured=true}else{status="Equipo asociado, sin mediciones";statusClass="no-data";configured=true;noData=true}actions='<button type="button" data-open-hanna>'+escapar(hasEquipment?"Ver equipo Hanna":"Asociar Hanna")+'</button>';
  }else{
   origin='<strong>Medición de plantas</strong>';visible="Sí";configured=true;noData=measurement.estado!=="ok";status=noData?"Configurado · Sin registros todavía":"Configurado";statusClass=noData?"no-data":"configured";actions='<button type="button" data-open-plants>Ver mediciones</button>';
  }
  return {definition,source,origin,technical,status,statusClass,visible,actions,configured,pending,noData};
 });
 const configured=rows.filter(item=>item.configured).length,pending=rows.filter(item=>item.pending).length,noData=rows.filter(item=>item.noData).length;$("#association-count").textContent=rows.length+" carteles · "+configured+" configurados · "+pending+" pendientes"+(noData?" · "+noData+" sin datos":"");
 $("#associations-body").innerHTML=rows.map(item=>'<tr data-configuration-key="'+escapar(item.definition.clave_educativa)+'"><td>'+escapar(item.definition.orden)+'</td><td><strong>'+escapar(item.definition.nombre_educativo)+'</strong><small>'+escapar(item.definition.clave_educativa)+'</small></td><td><span class="source-label '+escapar(item.source)+'">'+escapar(fuenteCartel(item.source))+'</span></td><td>'+item.origin+'</td><td><strong>'+escapar(item.technical||"—")+'</strong><small>'+escapar(item.definition.unidad||"—")+'</small></td><td><span class="configuration-state '+item.statusClass+'">'+escapar(item.status)+'</span></td><td>'+escapar(item.visible)+'</td><td><div class="row-actions">'+item.actions+'</div></td></tr>').join("");
 document.querySelectorAll("[data-edit]").forEach(button=>button.onclick=()=>editar(button.dataset.edit));document.querySelectorAll("[data-delete]").forEach(button=>button.onclick=()=>borrar(button.dataset.delete));document.querySelectorAll("[data-associate]").forEach(button=>button.onclick=()=>prepararAsociacion(button.dataset.associate));document.querySelectorAll("[data-open-hanna]").forEach(button=>button.onclick=abrirGestionHanna);document.querySelectorAll("[data-open-plants]").forEach(button=>button.onclick=abrirMedicionesPlantas);
}
function prepararAsociacion(key){const definition=posterState.catalogo.find(item=>item.clave_educativa===key);if(!definition)return;resetFormulario();$("#clave-educativa").value=definition.clave_educativa;$("#nombre-educativo").value=definition.nombre_educativo;$("#unidad").value=definition.unidad||"";$("#categoria").value=definition.categoria||"otra";$("#orden").value=definition.orden;$("#association-form").scrollIntoView({behavior:"smooth",block:"start"})}
function abrirGestionHanna(){seleccionarTab("hanna");document.querySelector(".hanna-equipment-panel")?.scrollIntoView({behavior:"smooth",block:"start"})}
function abrirMedicionesPlantas(){seleccionarTab("plants")}
function resetFormulario(){state.editando=null;$("#association-form").reset();$("#association-id").value="";$("#orden").value="1";$("#visible-frontend").checked=true;$("#form-title").textContent="Crear asociación";$("#cancel-edit").hidden=true;opcionesFormulario()}
function editar(id){const item=state.asociaciones.find(a=>(a._id||a.id)===id);if(!item)return;state.editando=id;Object.entries({"clave-educativa":item.clave_educativa,"nombre-educativo":item.nombre_educativo,"sensor-sn":item.sensor_sn,"variable-tecnica":item.variable_tecnica,"unidad":item.unidad,"categoria":item.categoria,"ubicacion":item.ubicacion,"profundidad-cm":item.profundidad_cm,"orden":item.orden}).forEach(([idCampo,valor])=>{$("#"+idCampo).value=valor??""});$("#visible-frontend").checked=Boolean(item.visible_frontend);$("#form-title").textContent="Editar asociación";$("#cancel-edit").hidden=false;actualizarVariablesFormulario();window.scrollTo({top:$("#association-form").offsetTop-100,behavior:"smooth"})}
function payloadFormulario(){const colegio=colegioActual();return {localidad:state.localidad,colegio_id:colegio?._id||null,device_sn:state.resumen?.device_sn||null,clave_educativa:$("#clave-educativa").value.trim(),nombre_educativo:$("#nombre-educativo").value.trim(),sensor_sn:$("#sensor-sn").value,variable_tecnica:$("#variable-tecnica").value,unidad:$("#unidad").value.trim(),categoria:$("#categoria").value,ubicacion:$("#ubicacion").value.trim()||null,profundidad_cm:$("#profundidad-cm").value===""?null:Number($("#profundidad-cm").value),visible_frontend:$("#visible-frontend").checked,orden:Number($("#orden").value)}}
function detalleErrorConsultaAsociaciones(error){if(error instanceof ApiError&&error.status>=400)return "Error HTTP "+error.status+" · "+error.message;return error?.message||"No se pudo conectar con FastAPI."}
async function consultarAsociaciones(carga=state.carga,localidad=state.localidad){state.cargandoAsociaciones=true;state.errorConsultaAsociaciones=null;renderAsociaciones();try{const data=await fetchAsociaciones(localidad);if(carga!==state.carga||localidad!==state.localidad)return false;if(!Array.isArray(data.items))throw new ApiError("La respuesta no contiene una lista de asociaciones utilizable",200);state.asociaciones=data.items;state.asociacionesVacias=!state.asociaciones.some(item=>(item.source||"zentra")==="zentra");state.apiAsociacionesDisponible=true;return true}catch(error){if(carga!==state.carga||localidad!==state.localidad)return false;state.asociaciones=[];state.asociacionesVacias=true;state.apiAsociacionesDisponible=false;state.errorConsultaAsociaciones=detalleErrorConsultaAsociaciones(error);return false}finally{if(carga===state.carga&&localidad===state.localidad){state.cargandoAsociaciones=false;renderAsociaciones()}}}
async function reintentarAsociaciones(){const ok=await consultarAsociaciones();if(ok){state.errorOperacionAsociacion=null;setStatus("success",state.asociacionesVacias?"API disponible · Sin asociaciones Zentra para este colegio":"Asociaciones Zentra consultadas correctamente.");await cargarVisorCarteles(true)}else setStatus("error","No fue posible consultar las asociaciones Zentra. "+state.errorConsultaAsociaciones)}
async function guardar(event){event.preventDefault();if(state.apiAsociacionesDisponible!==true)return;$("#save-button").disabled=true;state.errorOperacionAsociacion=null;setStatus("loading","Guardando asociación…");try{const payload=payloadFormulario();if(state.editando)await actualizarAsociacion(state.editando,payload);else await crearAsociacion(payload);resetFormulario();await cargarLocalidad("guardado")}catch(error){state.errorOperacionAsociacion=error.message;setStatus("error","No fue posible guardar la asociación. "+error.message);await consultarAsociaciones();renderAsociaciones()}}
async function borrar(id){if(state.apiAsociacionesDisponible!==true||!confirm("¿Eliminar esta asociación?"))return;state.errorOperacionAsociacion=null;setStatus("loading","Eliminando asociación…");try{await eliminarAsociacion(id);await cargarLocalidad("eliminado")}catch(error){state.errorOperacionAsociacion=error.message;setStatus("error","No fue posible eliminar la asociación. "+error.message);await consultarAsociaciones();renderAsociaciones()}}
async function cargarLocalidad(resultado){
 const carga=++state.carga;state.cargandoConfiguracion=true;state.cargandoAsociaciones=true;state.apiAsociacionesDisponible=null;state.asociacionesVacias=false;state.errorConsultaAsociaciones=null;state.errorOperacionAsociacion=null;state.resumen=null;state.sensores=[];state.variables=[];state.asociaciones=[];posterState.carga++;posterState.cargando=false;posterState.error=null;posterState.items=[];posterState.catalogo=[];renderContexto();renderSensores();renderAsociaciones();cargarVisorCarteles();setStatus("loading","Cargando información de "+localidades[state.localidad]+"…");$("#api-badge").className="badge neutral";$("#api-badge").textContent="Consultando API";
 try{
  const [colegios,sensores,variables,resumen]=await Promise.all([fetchColegios(),fetchSensores(),fetchVariables(),fetchResumenLocalidad(state.localidad)]);if(carga!==state.carga)return;
  state.colegios=colegios.items||[];state.sensoresCatalogo=sensores.items||[];state.variablesCatalogo=variables.items||[];state.resumen=resumen;state.sensores=agruparResumen(resumen.items||[]);state.variables=[...new Map((resumen.items||[]).filter(i=>i.variable).map(i=>[i.variable,{nombre:i.variable,unidad:i.units||""}])).values()];
  const asociacionesOk=await consultarAsociaciones(carga,state.localidad);if(carga!==state.carga)return;state.cargandoConfiguracion=false;renderContexto();renderSensores();resetFormulario();renderAsociaciones();$("#api-badge").className="badge "+(asociacionesOk?"ok":"warning");$("#api-badge").textContent=asociacionesOk?"API completa":"API parcial";
  if(resultado)setStatus("success",resultado==="guardado"?"Asociación guardada exitosamente.":"Asociación eliminada exitosamente.");else if(!asociacionesOk)setStatus("error","No fue posible consultar las asociaciones Zentra. "+state.errorConsultaAsociaciones);else if(!state.sensores.length)setStatus("empty","La localidad no tiene datos de sensores disponibles.");else setStatus("success","Información técnica cargada correctamente.");
 }catch(error){if(carga!==state.carga)return;state.cargandoConfiguracion=false;state.cargandoAsociaciones=false;state.resumen=null;state.sensores=[];state.variables=[];state.asociaciones=[];renderContexto();renderSensores();opcionesFormulario();renderAsociaciones();$("#api-badge").className="badge error";$("#api-badge").textContent="Sin conexión";setStatus("error","No fue posible conectar con FastAPI. Verifica que el backend esté activo.")}
}

function crearCamposPlantas(){
 $("#plants-inputs").innerHTML=Array.from({length:20},(_,index)=>{const numero=index+1;return '<fieldset class="plant-input"><legend>Planta '+numero+'</legend><label><span>Altura</span><div class="height-control"><input class="plant-measurement plant-height" data-plant="'+numero+'" type="number" min="0.1" step="0.1" inputmode="decimal" placeholder="0,0" aria-label="Altura en centímetros de planta '+numero+'"><span>cm</span></div></label></fieldset>'}).join("");
 document.querySelectorAll(".plant-height").forEach(input=>input.addEventListener("input",calcularPromedioDia));
}
function medicionesFormulario(){
 return [...document.querySelectorAll(".plant-height")].map(input=>input.value===""?null:{planta_numero:Number(input.dataset.plant),altura_cm:Number(input.value)}).filter(Boolean);
}
function calcularPromedioDia(){
 const alturas=[...document.querySelectorAll(".plant-height")].map(input=>Number(input.value)).filter(value=>Number.isFinite(value)&&value>0),promedio=alturas.length?alturas.reduce((suma,value)=>suma+value,0)/alturas.length:null;
 $("#daily-average").textContent=promedio===null?"—":promedio.toLocaleString("es-CL",{minimumFractionDigits:1,maximumFractionDigits:2});$("#measured-count").textContent=alturas.length+" "+(alturas.length===1?"planta medida":"plantas medidas");
}
function limpiarFormularioPlantas(){document.querySelectorAll(".plant-height").forEach(input=>input.value="");$("#plants-observation").value="";calcularPromedioDia()}
function rellenarFormularioPlantas(items){
 limpiarFormularioPlantas();items.forEach(item=>{const input=document.querySelector('.plant-height[data-plant="'+item.planta_numero+'"]');if(input&&item.altura_cm!=null)input.value=item.altura_cm});$("#plants-observation").value=items.find(item=>item.observacion)?.observacion||"";calcularPromedioDia();
}
function renderContextoPlantas(){
 const colegio=colegioPorLocalidad(plantState.localidad);$("#plants-colegio").textContent=colegio?.nombre||"Colegio no identificado";$("#plants-localidad-nombre").textContent=localidades[plantState.localidad];
}
function renderGraficoPlantas(){
 const items=plantState.promedios;$("#chart-count").textContent=items.length+" "+(items.length===1?"día":"días");
 if(!items.length){$("#plant-chart").innerHTML='<div class="chart-empty"><strong>Aún no hay mediciones de plantas para este huerto</strong><span>Guarda alturas para comenzar el historial real.</span></div>';$("#last-average").textContent="—";$("#last-average-date").textContent="Sin datos";return}
 const ultimo=items.at(-1);$("#last-average").textContent=Number(ultimo.altura_promedio_cm).toLocaleString("es-CL",{maximumFractionDigits:2});$("#last-average-date").textContent="Fecha "+ultimo.fecha+" · "+ultimo.plantas_medidas+" plantas medidas";
 const width=560,height=280,left=48,right=18,top=22,bottom=44,max=Math.max(...items.map(item=>item.altura_promedio_cm)),yMax=Math.max(5,Math.ceil(max/5)*5),x=(i)=>items.length===1?(left+width-right)/2:left+i*((width-left-right)/(items.length-1)),y=value=>top+(yMax-value)*((height-top-bottom)/yMax),points=items.map((item,i)=>x(i)+","+y(item.altura_promedio_cm)).join(" ");
 let svg='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Altura promedio diaria de plantas con fechas en el eje horizontal y centímetros en el eje vertical"><text class="axis-label" x="14" y="'+(height/2)+'" text-anchor="middle" transform="rotate(-90 14 '+(height/2)+')">Altura promedio (cm)</text>';
 [0,.25,.5,.75,1].forEach(ratio=>{const value=yMax*(1-ratio),py=top+ratio*(height-top-bottom);svg+='<line class="grid" x1="'+left+'" x2="'+(width-right)+'" y1="'+py+'" y2="'+py+'"/><text x="'+(left-8)+'" y="'+(py+4)+'" text-anchor="end">'+value.toFixed(value%1?1:0)+'</text>'});
 svg+='<polyline class="line" points="'+points+'"/>';items.forEach((item,i)=>{svg+='<circle class="point" cx="'+x(i)+'" cy="'+y(item.altura_promedio_cm)+'" r="5"><title>'+escapar(item.fecha)+': '+escapar(item.altura_promedio_cm)+' cm</title></circle>'});
 const etiquetas=[0,Math.floor((items.length-1)/2),items.length-1].filter((value,index,array)=>array.indexOf(value)===index);etiquetas.forEach(i=>{svg+='<text x="'+x(i)+'" y="'+(height-15)+'" text-anchor="middle">'+escapar(items[i].fecha.slice(5))+'</text>'});$("#plant-chart").innerHTML=svg+'</svg>';
}
async function cargarPromediosPlantas(mostrarEstado=true){
 const carga=++plantState.carga;renderContextoPlantas();$("#plant-chart").innerHTML='<p class="empty">Cargando promedios…</p>';
 if(mostrarEstado)setStatus("loading","Cargando mediciones de "+localidades[plantState.localidad]+"…");
 try{if(!state.colegios.length){const colegios=await fetchColegios();state.colegios=colegios.items||[];renderContextoPlantas()}const data=await fetchPromediosPlantas(plantState.localidad,30);if(carga!==plantState.carga)return;plantState.promedios=(data.items||[]).filter(item=>Number.isFinite(Number(item.altura_promedio_cm))&&Number(item.altura_promedio_cm)>0&&Number(item.plantas_medidas)>0).sort((a,b)=>a.fecha.localeCompare(b.fecha));renderGraficoPlantas();if(mostrarEstado)setStatus(plantState.promedios.length?"success":"empty",plantState.promedios.length?"Promedios reales de los últimos 30 días cargados.":"Aún no hay mediciones de plantas para este huerto.")}
 catch(error){if(carga!==plantState.carga)return;plantState.promedios=[];renderGraficoPlantas();setStatus("error","No fue posible cargar las mediciones de plantas: "+error.message)}
}
async function cargarMedicionesFecha(mostrarEstado=true){
 const carga=++plantState.cargaDia,fecha=$("#plants-fecha").value;limpiarFormularioPlantas();if(!fecha)return null;if(mostrarEstado)setStatus("loading","Buscando mediciones guardadas del "+fecha+"…");
 try{const data=await fetchMedicionesPlantas(plantState.localidad,fecha,"general");if(carga!==plantState.cargaDia)return null;plantState.mediciones=data.items||[];rellenarFormularioPlantas(plantState.mediciones);if(mostrarEstado)setStatus(plantState.mediciones.length?"success":"empty",plantState.mediciones.length?"Se recuperaron "+plantState.mediciones.length+" mediciones guardadas.":"No hay mediciones para esta fecha. El formulario está vacío.");return data}
 catch(error){if(carga!==plantState.cargaDia)return null;plantState.mediciones=[];limpiarFormularioPlantas();if(mostrarEstado)setStatus("error","No fue posible recuperar las mediciones: "+error.message);return null}
}
async function cargarVistaPlantas(){await cargarPromediosPlantas(false);await cargarMedicionesFecha(true)}
async function guardarPlantas(event){
 event.preventDefault();const mediciones=medicionesFormulario();
 if(!mediciones.length){setStatus("empty","Ingresa al menos una altura antes de guardar.");return}
 if(mediciones.some(item=>!Number.isFinite(item.altura_cm)||item.altura_cm<=0)){setStatus("error","La altura de cada planta medida debe ser un número positivo.");return}
 const boton=$("#save-plants"),colegio=colegioPorLocalidad(plantState.localidad),payload={localidad:plantState.localidad,colegio_id:colegio?._id||null,huerto_id:null,ciclo_id:"general",fecha:$("#plants-fecha").value,mediciones,observacion:$("#plants-observation").value.trim()||null};
 boton.disabled=true;boton.textContent="Guardando…";setStatus("loading","Guardando "+mediciones.length+" mediciones…");
 try{const result=await guardarMedicionesPlantas(payload),confirmacion=await cargarMedicionesFecha(false);await cargarPromediosPlantas(false);const confirmadas=confirmacion&&mediciones.every(enviada=>{const guardada=confirmacion.items.find(item=>item.planta_numero===enviada.planta_numero);return guardada&&Number(guardada.altura_cm)===enviada.altura_cm});if(!confirmadas)throw new Error("el servidor no devolvió todas las alturas guardadas");setStatus("success","Mediciones guardadas y verificadas: "+result.created+" nuevas y "+result.updated+" actualizadas.")}
 catch(error){setStatus("error","No fue posible guardar las mediciones: "+error.message)}finally{boton.disabled=false;boton.textContent="Guardar mediciones"}
}
function setHannaStatus(tipo,mensaje){const el=$("#hanna-status");el.className="status "+tipo;el.textContent=mensaje}
function fechaHoraLegible(valor){if(!valor)return "Sin cargas";const fecha=new Date(valor);return Number.isNaN(fecha.getTime())?valor:fecha.toLocaleString("es-CL")}
function metricaHanna(etiqueta,valor,clase=""){return '<div class="hanna-metric '+clase+'"><small>'+escapar(etiqueta)+'</small><strong>'+escapar(valor??"—")+'</strong></div>'}
function renderResultadoHanna(data){
 const warning=data.invalidos?'<p class="hanna-warning">El archivo fue cargado, pero contiene datos sospechosos. Revise el resumen.</p>':'';
  $("#hanna-result-content").innerHTML=warning+'<div class="hanna-result-grid">'+metricaHanna("Archivo",data.archivo_nombre)+metricaHanna("Localidad",localidades[data.localidad]||data.localidad)+metricaHanna("Equipo",data.equipo_modelo||"No informado")+metricaHanna("Serial",data.equipo_serial)+metricaHanna("Instrument ID",data.instrument_id||"No informado")+metricaHanna("Rango de fechas",data.fecha_inicio+" a "+data.fecha_fin)+metricaHanna("Registros leídos",data.registros_leidos)+metricaHanna("Insertados",data.insertados,"good")+metricaHanna("Duplicados detectados",data.duplicados??data.actualizados)+metricaHanna("Válidos",data.validos,"good")+metricaHanna("Sospechosos",data.invalidos,"warning")+'</div><div class="hanna-variables">'+data.variables_detectadas.map(variable=>'<span>'+escapar(variable)+'</span>').join("")+'</div>';
 $("#hanna-upload-result").hidden=false;
}
async function asegurarColegios(){if(state.colegios.length)return;const data=await fetchColegios();state.colegios=data.items||[]}
function opcionesColegios(seleccion=""){return '<option value="">Selecciona un colegio</option>'+state.colegios.map(item=>{const id=item._id||item.colegio_id||item.id;return '<option value="'+escapar(id)+'" '+(id===seleccion?"selected":"")+'>'+escapar(item.nombre||item.comuna)+'</option>'}).join("")}
function renderPreviewHanna(){const data=hannaState.preview,preview=$("#hanna-preview"),field=$("#hanna-college-field"),button=$("#hanna-submit");if(!data){preview.hidden=true;field.hidden=true;button.disabled=true;button.textContent="Analiza un archivo para continuar";$("#hanna-current-summary").innerHTML='<p class="empty">Selecciona un CSV para reconocer su equipo.</p>';return}preview.hidden=false;preview.innerHTML=metricaHanna("Modelo",data.modelo||"No informado")+metricaHanna("Serial",data.serial_hanna)+metricaHanna("Instrument ID",data.instrument_id||"No informado");field.hidden=data.asociado;if(!data.asociado)$("#hanna-colegio").innerHTML=opcionesColegios();button.disabled=false;button.textContent=data.asociado?"Cargar archivo":"Asociar equipo y cargar archivo";$("#hanna-current-summary").innerHTML=data.asociado?metricaHanna("Equipo",data.serial_hanna,"good")+metricaHanna("Huerto",data.equipo.colegio_nombre)+metricaHanna("Estado",data.equipo.estado):'<p class="empty">Este equipo Hanna todavía no está asociado. Selecciona el colegio correcto antes de cargar.</p>'}
async function analizarArchivoHanna(){const archivo=$("#hanna-file").files[0];hannaState.archivo=archivo||null;hannaState.preview=null;$("#hanna-upload-result").hidden=true;$("#hanna-file-name").textContent=archivo?.name||"Solo archivos .CSV";renderPreviewHanna();if(!archivo)return;setHannaStatus("loading","Analizando identidad del equipo…");try{await asegurarColegios();hannaState.preview=await analizarCsvHanna(archivo);renderPreviewHanna();setHannaStatus(hannaState.preview.asociado?"success":"empty",hannaState.preview.mensaje+(hannaState.preview.asociado?" · Huerto: "+hannaState.preview.equipo.localidad:""))}catch(error){setHannaStatus("error","No fue posible analizar el CSV: "+error.message)}}
function renderEquiposHanna(){$("#hanna-equipment-count").textContent=hannaState.equipos.length+" "+(hannaState.equipos.length===1?"equipo":"equipos");$("#hanna-equipment-list").innerHTML=hannaState.equipos.length?hannaState.equipos.map(item=>'<article class="hanna-equipment-card"><div><strong>'+escapar(item.serial_hanna)+'</strong><span>'+escapar(item.modelo)+' · ID '+escapar(item.instrument_id||"—")+'</span></div><div><strong>'+escapar(item.colegio_nombre)+'</strong><span>Asignado '+escapar(item.fecha_asignacion)+'</span></div><div><strong>'+escapar(item.estado)+'</strong><span>'+(item.reemplazado_por?"Reemplazado por "+escapar(item.reemplazado_por):"Equipo vigente")+'</span></div><div class="hanna-equipment-actions"><select data-hanna-college="'+escapar(item.serial_hanna)+'" aria-label="Colegio correcto">'+opcionesColegios(item.colegio_id)+'</select><button type="button" data-hanna-correct="'+escapar(item.serial_hanna)+'">Corregir asignación</button>'+(item.estado==="activo"?'<button type="button" data-hanna-replace="'+escapar(item.serial_hanna)+'">Reemplazar equipo</button>':"")+'</div></article>').join(""):'<p class="empty">Aún no hay equipos Hanna asociados.</p>';document.querySelectorAll("[data-hanna-correct]").forEach(button=>button.onclick=()=>corregirHanna(button.dataset.hannaCorrect));document.querySelectorAll("[data-hanna-replace]").forEach(button=>button.onclick=()=>reemplazarEquipoHanna(button.dataset.hannaReplace))}
async function cargarEquiposHanna(){try{await asegurarColegios();const data=await fetchDataloggersHanna();hannaState.equipos=data.items||[];renderEquiposHanna()}catch(error){$("#hanna-equipment-list").innerHTML='<p class="empty">No fue posible cargar los equipos: '+escapar(error.message)+'</p>'}}
async function corregirHanna(serial){const select=document.querySelector('[data-hanna-college="'+CSS.escape(serial)+'"]'),colegioId=select?.value,item=hannaState.equipos.find(e=>e.serial_hanna===serial),colegio=state.colegios.find(c=>(c._id||c.colegio_id||c.id)===colegioId);if(!colegioId||colegioId===item?.colegio_id)return;if(!confirm('¿Confirmas corregir la asignación de '+serial+' desde '+item.colegio_nombre+' a '+colegio.nombre+'?'))return;try{await corregirAsignacionHanna(serial,colegioId);await cargarEquiposHanna();await cargarVisorCarteles(true);setHannaStatus("success","Asignación corregida. Las mediciones ya pertenecen al nuevo huerto.")}catch(error){setHannaStatus("error","No fue posible corregir la asignación: "+error.message)}}
async function reemplazarEquipoHanna(serial){const nuevo=prompt("Serial del nuevo equipo Hanna que reemplaza a "+serial);if(!nuevo)return;const modelo=prompt("Modelo del nuevo equipo","HI981420")||"HI981420",instrumentId=prompt("Instrument ID del nuevo equipo","")||"";if(!confirm("¿Confirmas reemplazar "+serial+" por "+nuevo.toUpperCase()+"? El historial se conservará."))return;try{await reemplazarHanna(serial,{serial_hanna_nuevo:nuevo,modelo,instrument_id:instrumentId,fecha_asignacion:new Date().toISOString().slice(0,10)});await cargarEquiposHanna();await cargarVisorCarteles(true);setHannaStatus("success","Equipo reemplazado; el historial de ambos seriales se conserva.")}catch(error){setHannaStatus("error","No fue posible reemplazar el equipo: "+error.message)}}
async function subirHanna(event){
 event.preventDefault();const archivo=hannaState.archivo,preview=hannaState.preview;if(!archivo||!preview){setHannaStatus("empty","Selecciona y analiza un archivo CSV Hanna.");return}const colegioId=preview.asociado?null:$("#hanna-colegio").value;if(!preview.asociado&&!colegioId){setHannaStatus("empty","Selecciona el colegio al que pertenece este equipo.");return}
 const boton=$("#hanna-submit");boton.disabled=true;boton.textContent="Subiendo…";setHannaStatus("loading","Procesando "+archivo.name+"…");
 try{const data=await importarCsvHanna(archivo,colegioId);renderResultadoHanna(data);await cargarEquiposHanna();await cargarVisorCarteles(true);hannaState.preview=await analizarCsvHanna(archivo);renderPreviewHanna();setHannaStatus(data.invalidos?"empty":"success",data.invalidos?"Archivo cargado con "+data.invalidos+" registros sospechosos.":"Archivo cargado correctamente. Todos los registros son válidos.")}
 catch(error){setHannaStatus("error","No fue posible cargar el archivo: "+error.message)}finally{boton.disabled=false;boton.textContent=hannaState.preview?.asociado?"Cargar archivo":"Asociar equipo y cargar archivo"}
}
function setCampaignStatus(tipo,mensaje){const el=$("#campaign-status");el.className="status "+tipo;el.textContent=mensaje}
function renderCampanias(){const active=campaignState.activa?.estado==="activa"?campaignState.activa:null,activeBox=$("#campaign-active"),newPanel=document.querySelector(".campaign-new-panel"),newButton=$("#campaign-new-trigger"),help=$("#campaign-new-help"),blocked=Boolean(active);newButton.disabled=!campaignState.colegioId||blocked;help.hidden=!blocked;newPanel.hidden=(blocked&&campaignState.mode!=="edit")||!campaignState.formOpen;document.querySelector(".campaign-layout").classList.toggle("form-closed",newPanel.hidden);if(active){const elapsed=Math.max(0,Math.floor((Date.now()-Date.parse(active.fecha_siembra+"T00:00:00"))/86400000));activeBox.innerHTML='<div class="campaign-card"><h3>'+escapar(active.nombre)+'</h3><div class="campaign-details"><div><small>Cultivo</small><strong>'+escapar(active.cultivo)+'</strong></div><div><small>Estado</small><strong>'+escapar(active.estado)+'</strong></div><div><small>Siembra</small><strong>'+escapar(active.fecha_siembra)+'</strong></div><div><small>Días transcurridos</small><strong>'+elapsed+'</strong></div><div><small>Cosecha estimada</small><strong>'+escapar(active.fecha_cosecha_estimada)+'</strong></div><div><small>Observaciones</small><strong>'+escapar(active.observaciones||"Sin observaciones")+'</strong></div></div><div class="campaign-actions"><button class="primary-button" type="button" id="campaign-edit">Editar campaña</button><button class="primary-button" type="button" id="campaign-finish">Finalizar campaña</button><button class="primary-button danger" type="button" id="campaign-cancel">Cancelar campaña</button></div></div>';$("#campaign-edit").onclick=editarCampaniaActiva;$("#campaign-finish").onclick=finalizarCampaniaActiva;$("#campaign-cancel").onclick=cancelarCampaniaActiva}else activeBox.innerHTML='<p class="empty">Este colegio no tiene una campaña activa. Usa “+ Nueva campaña” para comenzar.</p>';const history=campaignState.items.filter(item=>item.estado!=="activa");$("#campaign-count").textContent=campaignState.items.length+" "+(campaignState.items.length===1?"campaña":"campañas");$("#campaign-history").innerHTML=history.length?'<div class="campaign-history-list">'+history.map(item=>'<details class="campaign-history-item"><summary><strong>'+escapar(item.nombre)+'</strong><span>'+escapar(item.cultivo)+'</span></summary><div><small>Siembra</small><strong>'+escapar(item.fecha_siembra||"—")+'</strong></div><div><small>Cosecha real</small><strong>'+escapar(item.fecha_cosecha_real||"—")+'</strong></div><div><small>Estado</small><strong>'+escapar(item.estado)+'</strong></div></details>').join("")+'</div>':'<p class="empty">Sin campañas anteriores.</p>'}
async function prepararSelectorCampanias(){await asegurarColegios();const select=$("#campaign-college");if(!campaignState.colegioId)campaignState.colegioId=colegioActual()?._id||state.colegios[0]?._id||"";select.innerHTML=opcionesColegios(campaignState.colegioId);select.value=campaignState.colegioId}
async function cargarCampanias(estricto=false){const id=campaignState.colegioId;if(!id)return;const carga=++campaignState.carga;setCampaignStatus("loading","Consultando campañas…");try{const [all,active]=await Promise.all([fetchCampanias(id),fetchCampaniaActiva(id)]);if(carga!==campaignState.carga)return;campaignState.items=all.items||[];campaignState.activa=campaignState.items.find(item=>item.estado==="activa")||(active.item?.estado==="activa"?active.item:null);if(campaignState.activa)campaignState.formOpen=false;renderCampanias();setCampaignStatus(campaignState.activa?"success":"empty",campaignState.activa?"Campaña activa cargada.":"No hay campaña activa para este colegio.")}catch(error){if(estricto)throw error;campaignState.activa=null;campaignState.items=[];campaignState.formOpen=false;renderCampanias();setCampaignStatus("error","No fue posible cargar las campañas: "+error.message)}}
const campaignFields={nombre:"#campaign-name",cultivo:"#campaign-crop",fecha_siembra:"#campaign-sowing",fecha_cosecha_estimada:"#campaign-estimated",observaciones:"#campaign-notes"};
function erroresCampania(form,fields={}){
 form.querySelectorAll("[data-campaign-error]").forEach(el=>{const field=el.dataset.campaignError;el.textContent=fields[field]||"";el.id="error-"+form.id+"-"+field;const input=form.elements.namedItem(field);if(input){input.setAttribute("aria-describedby",el.id);input.setAttribute("aria-invalid",String(Boolean(fields[field])))}});
}
function bloquearCampania(busy){
 campaignState.busy=busy;
 $("#campaign-college").disabled=busy;
 document.querySelectorAll("#campaign-form input,#campaign-form textarea,#campaign-form button,#campaign-finish-form input,#campaign-finish-form textarea,#campaign-finish-form button,.campaign-actions button").forEach(el=>el.disabled=busy);
 $("#campaign-new-trigger").disabled=busy||!campaignState.colegioId||Boolean(campaignState.activa);
 $("#campaign-submit").textContent=busy?"Guardando…":campaignState.mode==="edit"?"Guardar cambios":"Iniciar campaña";
 $("#campaign-finish-submit").textContent=busy?"Finalizando…":"Confirmar finalización";
}
function abrirFormularioCampania(mode){
 if(campaignState.busy)return;
 const item=mode==="edit"?campaignState.activa:null;
 if(mode==="edit"&&item?.estado!=="activa")return;
 campaignState.mode=mode;campaignState.editing=item?{...item}:null;campaignState.finishing=null;
 $("#campaign-finish-panel").hidden=true;
 const form=$("#campaign-form");form.reset();form.dataset.mode=mode;erroresCampania(form);
 $("#campaign-form-context").textContent=mode==="edit"?"Campaña activa":"Nuevo ciclo";
 $("#campaign-form-title").textContent=mode==="edit"?"Editar campaña":"Iniciar campaña";
 $("#campaign-submit").textContent=mode==="edit"?"Guardar cambios":"Iniciar campaña";
 $("#campaign-name-field").hidden=mode!=="edit";
 $("#campaign-name").disabled=mode!=="edit";
 for(const [field,selector] of Object.entries(campaignFields)){
  const input=$(selector),value=String(item?.[field]??"");
  input.value=input.type==="date"?value.slice(0,10):value;
  // Historical missing values remain absent unless the user supplies them.
  input.required=field!=="observaciones"&&(field!=="nombre"||mode==="edit")&&(mode!=="edit"||Boolean(item?.[field]));
 }
 campaignState.formOpen=true;renderCampanias();
 $(mode==="edit"?"#campaign-name":"#campaign-crop").focus();
}
function editarCampaniaActiva(){abrirFormularioCampania("edit")}
async function iniciarCampania(event){
 event.preventDefault();if(campaignState.busy||!campaignState.colegioId)return;
 const editing=campaignState.mode==="edit"?campaignState.editing:null;
 if(!editing&&campaignState.activa?.estado==="activa")return;
 const form=event.target,values={},fields={};
 for(const [field,selector] of Object.entries(campaignFields)){
  if(field==="nombre"&&!editing)continue;
  const input=$(selector);values[field]=input.value.trim();
  if(input.required&&!values[field])fields[field]="Complete este campo.";
  if(input.maxLength>0&&values[field].length>input.maxLength)fields[field]="El texto supera el largo permitido.";
 }
 if(values.fecha_siembra&&values.fecha_cosecha_estimada&&values.fecha_cosecha_estimada<values.fecha_siembra)fields.fecha_cosecha_estimada="La cosecha estimada no puede ser anterior a la siembra.";
 erroresCampania(form,fields);
 if(Object.keys(fields).length){setCampaignStatus("error","Revise los campos indicados.");return}
 const payload=editing?{revision:editing.revision??0}:{colegio_id:campaignState.colegioId};
 for(const [field,value] of Object.entries(values)){
  const before=String(editing?.[field]??"");
  if(!editing||value!==(field.startsWith("fecha_")?before.slice(0,10):before))payload[field]=value;
 }
 if(editing&&Object.keys(payload).length===1){setCampaignStatus("empty","No hay cambios para guardar.");return}
 bloquearCampania(true);
 try{
  if(editing)await actualizarCampania(editing._id,payload);else await crearCampania(payload);
  await cargarCampanias(true);campaignState.formOpen=false;renderCampanias();
  setCampaignStatus("success",editing?"Campaña actualizada correctamente.":"Campaña iniciada correctamente.");
 }catch(error){erroresCampania(form,error.fields);setCampaignStatus("error",error.message||"No fue posible guardar la campaña. Revise los datos e inténtelo nuevamente.")}
 finally{bloquearCampania(false)}
}
function finalizarCampaniaActiva(){
 if(campaignState.busy||campaignState.activa?.estado!=="activa")return;
 campaignState.finishing={...campaignState.activa};campaignState.formOpen=false;renderCampanias();
 const form=$("#campaign-finish-form");form.reset();erroresCampania(form);
 $("#campaign-finish-date").min=(campaignState.finishing.fecha_siembra||"").slice(0,10);
 $("#campaign-finish-panel").hidden=false;$("#campaign-finish-date").focus();
}
async function confirmarFinalizacion(event){
 event.preventDefault();if(campaignState.busy||!campaignState.finishing)return;
 const form=event.target,item=campaignState.finishing,fields={};
 const payload={fecha_cosecha_real:$("#campaign-finish-date").value.trim(),resultado_final:$("#campaign-finish-result").value.trim(),observaciones_finales:$("#campaign-finish-notes").value.trim(),confirmar:$("#campaign-finish-confirm").checked,revision:item.revision??0};
 if(!payload.fecha_cosecha_real)fields.fecha_cosecha_real="Debe indicar la fecha real de término.";
 else if(item.fecha_siembra&&payload.fecha_cosecha_real<item.fecha_siembra.slice(0,10))fields.fecha_cosecha_real="La cosecha real no puede ser anterior a la siembra.";
 if(payload.resultado_final.length<3)fields.resultado_final="Debe escribir un resumen de la campaña de al menos 3 caracteres.";
 if(payload.resultado_final.length>3000)fields.resultado_final="El resumen no puede superar 3000 caracteres.";
 if(payload.observaciones_finales.length>3000)fields.observaciones_finales="Las observaciones no pueden superar 3000 caracteres.";
 if(!payload.confirmar)fields.confirmar="Debe confirmar explícitamente la finalización.";
 erroresCampania(form,fields);
 if(Object.keys(fields).length){setCampaignStatus("error",Object.values(fields).join(" "));return}
 bloquearCampania(true);
 try{
  await finalizarCampania(item._id,payload);
  await cargarCampanias(true);
  campaignState.finishing=null;$("#campaign-finish-panel").hidden=true;campaignState.formOpen=false;renderCampanias();
  setCampaignStatus("success","Campaña finalizada y trasladada al historial.");
 }catch(error){erroresCampania(form,error.fields);setCampaignStatus("error",error.message||"No fue posible finalizar la campaña. Revise los datos e inténtelo nuevamente.")}
 finally{bloquearCampania(false)}
}
async function cancelarCampaniaActiva(){if(!confirm("¿Confirmas cancelar esta campaña? Sus datos históricos se conservarán."))return;try{await cancelarCampania(campaignState.activa._id);campaignState.formOpen=false;await cargarCampanias();setCampaignStatus("success","Campaña cancelada y conservada en el historial.")}catch(error){setCampaignStatus("error","No fue posible cancelar: "+error.message)}}
function seleccionarTab(nombre){
 document.querySelectorAll("[data-tab]").forEach(button=>{const activa=button.dataset.tab===nombre;button.classList.toggle("active",activa);button.setAttribute("aria-selected",String(activa))});document.querySelectorAll(".tab-view").forEach(view=>view.hidden=view.id!==nombre+"-view");
 if(nombre==="plants"){plantState.localidad=state.localidad;$("#plants-localidad").value=plantState.localidad;renderContextoPlantas();cargarVistaPlantas()}else if(nombre==="hanna")cargarEquiposHanna();else if(nombre==="campaigns")prepararSelectorCampanias().then(cargarCampanias);else setStatus(state.sensores.length?"success":"empty",state.sensores.length?"Información técnica cargada correctamente.":"La localidad no tiene datos de sensores disponibles.");
}

$("#localidad").onchange=event=>{state.localidad=event.target.value;resetFormulario();cargarLocalidad()};
$("#sensor-sn").onchange=()=>{$("#ubicacion").value="";actualizarVariablesFormulario()};
$("#variable-tecnica").onchange=actualizarUnidad;
$("#association-form").onsubmit=guardar;
$("#cancel-edit").onclick=resetFormulario;
$("#test-associations").onclick=cargarVisorCarteles;
$("#retry-associations").onclick=reintentarAsociaciones;
document.querySelectorAll("[data-tab]").forEach(button=>button.onclick=()=>seleccionarTab(button.dataset.tab));
$("#plants-localidad").onchange=event=>{plantState.localidad=event.target.value;cargarVistaPlantas()};
$("#plants-fecha").onchange=()=>cargarMedicionesFecha(true);
$("#plants-form").onsubmit=guardarPlantas;
$("#hanna-file").onchange=analizarArchivoHanna;
$("#hanna-form").onsubmit=subirHanna;
$("#campaign-college").onchange=event=>{if(campaignState.busy)return;campaignState.colegioId=event.target.value;campaignState.formOpen=false;campaignState.finishing=null;$("#campaign-finish-panel").hidden=true;cargarCampanias()};
$("#campaign-new-trigger").onclick=()=>{if(!campaignState.activa&&campaignState.colegioId){abrirFormularioCampania("create")}};
$("#campaign-form-cancel").onclick=()=>{campaignState.formOpen=false;renderCampanias()};
$("#campaign-form").onsubmit=iniciarCampania;
$("#campaign-finish-form").onsubmit=confirmarFinalizacion;
$("#campaign-finish-close").onclick=()=>{if(!campaignState.busy){campaignState.finishing=null;$("#campaign-finish-panel").hidden=true}};
$("#plants-fecha").value=new Date().toISOString().slice(0,10);
crearCamposPlantas();
cargarLocalidad();
