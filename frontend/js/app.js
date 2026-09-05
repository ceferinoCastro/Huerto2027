import {localidades,sensores} from "./datos-demo.js?v=6";
import {fetchHistorialEducativo,fetchUltimasEducativas} from "./api.js?v=7";
import {svgGrafico,svgGraficoAltura,svgGraficoTemperaturaAgua,svgGraficoTemperaturas} from "./graficos.js?v=5";
import {SENSOR_CARD_CATALOG,SENSOR_GROUP_CATALOG} from "./catalogo-carteles.js?v=2";
import {estadoCartel} from "./estado-carteles.js?v=1";

let localidad="colchane",colegioId=null,selectedEducationalVariableKey=null,categoriaActiva="temperatura",periodo="7d",dashboard={items:[]},historiales={},estadosHistorial={},cicloCarga=0;
const horasPeriodo={"24h":24,"7d":168,"30d":720};
const grupos={
 temperatura:{titulo:"TEMPERATURA",icono:"🌡️",color:"#ee5918",claves:["temperatura_aire","temperatura_tierra","temperatura_bajo_tierra","temperatura_agua"],botones:["Aire","Tierra","Bajo tierra","Agua"]},
 humedad:{titulo:"HUMEDAD",icono:"💧",color:"#1388c4",claves:["humedad_aire","humedad_tierra","humedad_hojas"],botones:["☁️","💧","🍃"]},
 crecimiento:{titulo:"CRECIMIENTO",icono:"🌱",color:"#62a72c",claves:["altura_planta"],botones:["Altura promedio"]},
 agua:{titulo:"CALIDAD DEL AGUA",icono:"💧",color:"#7d3b96",claves:["ph_agua","sales_agua"],botones:["pH","SAL"]}
};
const categorias={temperatura:{etiqueta:"Temperatura",icono:"🌡️"},humedad:{etiqueta:"Humedad",icono:"💧"},crecimiento:{etiqueta:"Crecimiento",icono:"🌱"},agua:{etiqueta:"Calidad del agua",icono:"🧪"}};
const nombresFuente={zentra:"Sensor del huerto",hanna:"Equipo de medición del agua",manual:"Medición realizada por estudiantes o docentes"};
const modos={temperatura:"temperatura_aire",humedad:"all",crecimiento:"altura_planta",agua:"ph_agua"};
const $=selector=>document.querySelector(selector);
const clavesEducativas=Object.keys(sensores);
const itemsResumen=()=>Array.isArray(dashboard?.items)?dashboard.items:[];
const variable=clave=>itemsResumen().find(item=>item.variable===clave)||null;
const convertirValor=(clave,valor,unidades)=>clave==="humedad_tierra"&&unidades==="m³/m³"?Number(valor)*100:Number(valor);
const unidadVisible=(clave,unidad)=>clave==="humedad_tierra"&&unidad==="m³/m³"?"%":unidad||sensores[clave]?.unidad||"";
const colegioActual=()=>localidades[localidad].colegio;

const iconosCartel={
 temperature:'<path d="M12 4v10.2a4 4 0 1 0 4 0V4a2 2 0 0 0-4 0Z"/><path d="M14 8v8"/>',
 humidity:'<path d="M12 3C9 7.2 6.5 10 6.5 14a5.5 5.5 0 0 0 11 0C17.5 10 15 7.2 12 3Z"/><path d="M9.5 15.5c.5 1 1.3 1.5 2.5 1.5"/>',
 "leaf-water":'<path d="M4 15C5 8 10 4 19 5c0 8-4 13-11 13"/><path d="M5 20c3-5 7-8 12-11"/><path d="M18 14c-1.4 2-2.2 3.2-2.2 4.3a2.2 2.2 0 0 0 4.4 0C20.2 17.2 19.4 16 18 14Z"/>',
 "temperature-soil":'<path d="M10 4v9.8a4 4 0 1 0 4 0V4a2 2 0 0 0-4 0Z"/><path d="M12 9v7"/><path d="M3 19h5m8 0h5"/>',
 "temperature-depth":'<path d="M10 3v10.8a4 4 0 1 0 4 0V3a2 2 0 0 0-4 0Z"/><path d="M12 10v6"/><path d="M4 7h3M3 11h4M2 15h5"/>',
 "soil-water":'<path d="M3 17c3-2 5 2 8 0s5 2 10 0"/><path d="M3 21c3-2 5 2 8 0s5 2 10 0"/><path d="M12 3C9.8 6 8.5 7.8 8.5 10a3.5 3.5 0 0 0 7 0C15.5 7.8 14.2 6 12 3Z"/>',
 "ph-water":'<path d="M12 3C8.7 7.5 6 10.4 6 14.5a6 6 0 0 0 12 0C18 10.4 15.3 7.5 12 3Z"/><text x="12" y="16.5">pH</text>',
 "salts-water":'<path d="M7 5l5-3 5 3v6l-5 3-5-3Z"/><path d="m7 5 5 3 5-3M12 8v6M4 19c3-2 5 2 8 0s5 2 8 0"/>',
 "temperature-water":'<path d="M7 4v10.2a4 4 0 1 0 4 0V4a2 2 0 0 0-4 0Z"/><path d="M9 9v7"/><path d="M18 8c-2 2.8-3 4.2-3 5.6a3 3 0 0 0 6 0C21 12.2 20 10.8 18 8Z"/>',
 "plant-height":'<path d="M7 21V3m-2 3h4M5 11h4M5 16h4"/><path d="M14 21v-8m0 3c-4 0-5-2-5-5 4 0 5 2 5 5Zm0-3c4 0 5-2 5-5-4 0-5 2-5 5Z"/>',
 "root-length":'<path d="M12 3v18m0-13-4 4m4 1 5 4m-5 0-3 3"/><path d="M5 3h14M5 6h3m8 0h3"/>',
};
function iconoCartel(nombre){
 return '<svg class="sensor-card__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'+iconosCartel[nombre]+'</svg>';
}
function puntoAnclaje(item){
 const {x,y}=item.position.desktop,desplazamientos={top:{x:0,y:-2.7},right:{x:7.2,y:0},bottom:{x:0,y:2.7},left:{x:-7.2,y:0}},desplazamiento=desplazamientos[item.anchor];
 return {x:x+desplazamiento.x,y:y+desplazamiento.y};
}
function trazadoConexion(item){
 const inicio=puntoAnclaje(item),destino=item.target,ruta=item.route||[];
 if(ruta.length===1)return `M ${inicio.x} ${inicio.y} Q ${ruta[0].x} ${ruta[0].y} ${destino.x} ${destino.y}`;
 if(ruta.length>=2)return `M ${inicio.x} ${inicio.y} C ${ruta[0].x} ${ruta[0].y} ${ruta[1].x} ${ruta[1].y} ${destino.x} ${destino.y}`;
 return `M ${inicio.x} ${inicio.y} L ${destino.x} ${destino.y}`;
}
function reglaMedicion(item){
 const regla=item.ruler,direccion=regla.tickSide==="left"?-1:1,marcas=Array.from({length:7},(_,indice)=>{const proporcion=indice/6,y=regla.y1+(regla.y2-regla.y1)*proporcion,largo=indice%3===0?1.5:.9;return '<line class="sensor-ruler__tick" x1="'+regla.x+'" y1="'+y+'" x2="'+(regla.x+direccion*largo)+'" y2="'+y+'"/>'}).join("");
 return '<g id="'+regla.id+'" class="sensor-ruler" data-sensor-ruler="'+regla.id+'" data-sensor-keys="'+item.key+'"><line class="sensor-ruler__spine" x1="'+regla.x+'" y1="'+regla.y1+'" x2="'+regla.x+'" y2="'+regla.y2+'"/>'+marcas+'</g>';
}
function clavesElemento(elemento){return (elemento.dataset.sensorKeys||elemento.dataset.sensorCard||"").split(" ").filter(Boolean)}
function restaurarCarteles(){
 if(selectedEducationalVariableKey){aplicarResaltado([selectedEducationalVariableKey]);return}
 $(".huerto-scene")?.classList.remove("has-sensor-selection");
 document.querySelectorAll('[data-sensor-card],[data-sensor-marker],[data-sensor-target],[data-sensor-ruler]').forEach(elemento=>{elemento.classList.remove("is-highlighted","is-muted","is-selected");if(elemento.matches("button"))elemento.setAttribute("aria-pressed","false")});
}
function aplicarResaltado(claves){
 const activas=new Set(claves);$(".huerto-scene")?.classList.add("has-sensor-selection");
 document.querySelectorAll('[data-sensor-card],[data-sensor-marker],[data-sensor-target],[data-sensor-ruler]').forEach(elemento=>{const coincide=clavesElemento(elemento).some(clave=>activas.has(clave)),esCartelSeleccionado=elemento.dataset.sensorCard===selectedEducationalVariableKey;elemento.classList.toggle("is-highlighted",coincide);elemento.classList.toggle("is-muted",!coincide);elemento.classList.toggle("is-selected",esCartelSeleccionado);if(elemento.matches("button"))elemento.setAttribute("aria-pressed",String(elemento.dataset.sensorCard?esCartelSeleccionado:coincide))});
}
function desplazarPanelMovil(){
 const panel=$("#educational-detail-panel");if(!panel||!window.matchMedia("(max-width: 768px)").matches)return;const rect=panel.getBoundingClientRect(),margenSuperior=90,visible=rect.top>=margenSuperior&&rect.bottom<=window.innerHeight;if(!visible)panel.scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"})
}
function seleccionarVariableEducativa(clave,{desplazarPanel=false}={}){
 const item=SENSOR_CARD_CATALOG.find(sensor=>sensor.key===clave);if(!item)return;selectedEducationalVariableKey=clave;renderEducationalState();anunciarCarteles(item.label+": "+estadoCartel(variable(clave),item).text);if(desplazarPanel)desplazarPanelMovil()
}
function resaltarCartel(clave,{desplazar=false,enfocar=false}={}){
 seleccionarVariableEducativa(clave,{desplazarPanel:desplazar});const cartel=document.querySelector(`[data-sensor-card="${clave}"]`);
 if(enfocar)cartel?.focus({preventScroll:true});
}
function resaltarMarcador(marcador){
 const primera=clavesElemento(marcador)[0];seleccionarVariableEducativa(primera,{desplazarPanel:true});
}
function crearCartelesVisuales(){
 const conexiones=$(".huerto-scene__connections"),marcadores=$(".huerto-scene__markers"),carteles=$(".huerto-scene__cards");
 const objetivos=[...SENSOR_CARD_CATALOG.reduce((mapa,item)=>{const id=item.sharedTarget||item.key,actual=mapa.get(id)||{id,items:[]};actual.items.push(item);mapa.set(id,actual);return mapa},new Map()).values()];
 const reglas=SENSOR_CARD_CATALOG.filter(item=>item.ruler).map(reglaMedicion).join("");
 conexiones.innerHTML=reglas+objetivos.map(objetivo=>{const item=objetivo.items.find(sensor=>sensor.showConnection)||objetivo.items[0],claves=objetivo.items.map(sensor=>sensor.key).join(" "),linea=item.showConnection?'<path d="'+trazadoConexion(item)+'"/>':"";return '<g class="sensor-connection" data-sensor-target="'+objetivo.id+'" data-sensor-keys="'+claves+'">'+linea+'<circle cx="'+item.target.x+'" cy="'+item.target.y+'" r=".65"/><circle class="sensor-connection__pulse" cx="'+item.target.x+'" cy="'+item.target.y+'" r="1.25"/></g>'}).join("");
 marcadores.innerHTML=objetivos.map((objetivo,indice)=>{const item=objetivo.items[0],claves=objetivo.items.map(sensor=>sensor.key).join(" "),etiqueta=objetivo.items.length>1?SENSOR_GROUP_CATALOG.find(grupo=>grupo.key===item.group).label:item.label;return '<button type="button" class="sensor-marker" data-sensor-marker="'+objetivo.id+'" data-sensor-keys="'+claves+'" style="--marker-x:'+item.target.x+'%;--marker-y:'+item.target.y+'%;--marker-accent:'+SENSOR_GROUP_CATALOG.find(grupo=>grupo.key===item.group).accent+'" aria-label="Ver '+etiqueta+'" aria-pressed="false"><span aria-hidden="true">'+(indice+1)+'</span></button>'}).join("");
 carteles.innerHTML=SENSOR_GROUP_CATALOG.map(grupo=>{const items=SENSOR_CARD_CATALOG.filter(item=>item.group===grupo.key),tarjetas=items.map(item=>{const descripcionRegla=item.ruler?'. '+item.ruler.label:"";return '<button type="button" class="sensor-card sensor-card--neutral" data-sensor-card="'+item.key+'" data-measurement-state="loading" style="--card-x:'+item.position.desktop.x+';--card-y:'+item.position.desktop.y+';--mobile-order:'+item.position.mobile.order+'" aria-label="'+item.label+'. Cargando'+descripcionRegla+'" aria-pressed="false">'+iconoCartel(item.icon)+'<span class="sensor-card__copy"><span class="sensor-card__label">'+item.label+'</span><span class="sensor-card__value" data-sensor-value>Cargando…</span></span></button>'}).join("");return '<section class="sensor-group" data-sensor-group="'+grupo.key+'" style="--group-accent:'+grupo.accent+'"><h3 class="sensor-group__title">'+grupo.label+'</h3>'+tarjetas+'</section>'}).join("");
 document.querySelectorAll("[data-sensor-marker]").forEach(marcador=>marcador.addEventListener("click",()=>resaltarMarcador(marcador)));
 document.querySelectorAll("[data-sensor-card]").forEach((cartel,indice)=>{cartel.addEventListener("click",()=>resaltarCartel(cartel.dataset.sensorCard,{desplazar:true}));cartel.addEventListener("keydown",evento=>{if(!["ArrowRight","ArrowDown","ArrowLeft","ArrowUp"].includes(evento.key))return;evento.preventDefault();const paso=["ArrowRight","ArrowDown"].includes(evento.key)?1:-1,carteles=[...document.querySelectorAll("[data-sensor-card]")],siguiente=(indice+paso+carteles.length)%carteles.length;carteles[siguiente].focus()})});
 document.addEventListener("pointerdown",evento=>{if(!evento.target.closest("[data-sensor-card],[data-sensor-marker]"))restaurarCarteles()});
 document.addEventListener("keydown",evento=>{if(evento.key==="Escape"){selectedEducationalVariableKey=null;renderEducationalState()}});
}

function actualizarRegla(item,estado){
 if(!item.ruler)return;const regla=document.querySelector(`[data-sensor-ruler="${item.ruler.id}"]`);if(!regla)return;
 regla.dataset.measurementState=estado.status;regla.removeAttribute("data-measurement-value");regla.removeAttribute("data-measurement-unit");regla.removeAttribute("data-measurement-datetime");
 if(estado.status==="available"){regla.dataset.measurementValue=String(estado.value);regla.dataset.measurementUnit=estado.unit;regla.dataset.measurementDatetime=estado.datetime||""}
}
function actualizarCarteles(items){
 const lecturas=new Map((Array.isArray(items)?items:[]).map(item=>[item?.variable,item]));
 SENSOR_CARD_CATALOG.forEach(item=>{const cartel=document.querySelector(`[data-sensor-card="${item.key}"]`),valor=cartel?.querySelector("[data-sensor-value]"),estado=estadoCartel(lecturas.get(item.key),item);if(!cartel||!valor)return;valor.textContent=estado.text;cartel.dataset.measurementState=estado.status;cartel.dataset.measurementSource=estado.source||"";cartel.title=estado.updatedText;const descripcionRegla=item.ruler?`. ${item.ruler.label}`:"",actualizacion=estado.updatedText?`. ${estado.updatedText}`:"";cartel.setAttribute("aria-label",`${item.label}. ${estado.text}${actualizacion}${descripcionRegla}`);actualizarRegla(item,estado)});
}
function anunciarCarteles(mensaje){const estado=$("#educational-detail-status");if(estado)estado.textContent=mensaje}

function renderSelectedVariableDetail(){
 const panel=$("#educational-detail-panel"),contexto=$("#educational-detail-context"),envolturaValor=$("#educational-detail-value-wrap"),filaFecha=$("#educational-detail-date-row");if(!panel)return;
 const limpiar=()=>{$("#educational-detail-value").textContent="";$("#educational-detail-unit").textContent="";$("#educational-detail-date").textContent="";$("#educational-detail-source").textContent="";$("#educational-detail-school").textContent="";$("#educational-detail-locality").textContent="";$("#educational-detail-explanation").textContent=""};limpiar();
 const item=SENSOR_CARD_CATALOG.find(sensor=>sensor.key===selectedEducationalVariableKey);
 if(!item){panel.dataset.detailState="empty";panel.className="educational-detail educational-detail--empty";panel.style.removeProperty("--detail-accent");$("#educational-detail-icon").textContent="⌕";$("#educational-detail-state").textContent="Explora el huerto";$("#educational-detail-title").textContent="Explora el huerto";$("#educational-detail-message").textContent="Selecciona un cartel para conocer esta medición.";envolturaValor.hidden=true;contexto.hidden=true;filaFecha.hidden=true;restaurarCarteles();return}
 const lectura=variable(item.key),estado=estadoCartel(lectura,item),grupo=SENSOR_GROUP_CATALOG.find(grupo=>grupo.key===item.group),iconoPanel=$("#educational-detail-icon"),iconoSeleccionado=document.querySelector(`[data-sensor-card="${item.key}"] .sensor-card__icon`);panel.dataset.detailState=estado.status;panel.className="educational-detail educational-detail--"+estado.status;panel.style.setProperty("--detail-accent",grupo?.accent||"#31564c");iconoPanel.replaceChildren();if(iconoSeleccionado)iconoPanel.append(iconoSeleccionado.cloneNode(true));$("#educational-detail-title").textContent=item.label;$("#educational-detail-school").textContent=colegioActual()||"Nombre no disponible";$("#educational-detail-locality").textContent=localidades[localidad]?.nombre||"Localidad no disponible";$("#educational-detail-source").textContent=nombresFuente[estado.source]||"Fuente no disponible";$("#educational-detail-explanation").textContent=item.explanation;contexto.hidden=false;
 const etiquetas={loading:"Cargando información…",available:"Dato disponible",no_data:"Sin datos disponibles",error:"Sin conexión"},mensajes={loading:"Cargando información…",available:"",no_data:"Todavía no existe una medición de esta variable para el huerto seleccionado.",error:"No fue posible conectar con el servidor. Puedes intentar nuevamente con el botón Actualizar."};$("#educational-detail-state").textContent=etiquetas[estado.status];$("#educational-detail-message").textContent=mensajes[estado.status];envolturaValor.hidden=estado.status!=="available";filaFecha.hidden=estado.status!=="available";
 if(estado.status==="available"){$("#educational-detail-value").textContent=estado.formattedValue;$("#educational-detail-unit").textContent=estado.unit;$("#educational-detail-date").textContent=estado.updatedText?estado.updatedText.replace(/^Actualizado:\s*/,""):"Fecha no disponible"}
 aplicarResaltado([item.key]);
}
function renderEducationalState(){actualizarCarteles(itemsResumen());renderSelectedVariableDetail()}

function estadoInicial(estado="cargando"){
 return {items:clavesEducativas.map(clave=>({variable:clave,nombre:sensores[clave].nombre,valor:null,unidad:sensores[clave].unidad,estado,fuente:null,colegio_id:null}))};
}
function valoresHistorial(clave){
 const historial=historiales[clave];
 return (historial?.items||[]).map(item=>convertirValor(clave,item?.value,historial?.unidad)).filter(Number.isFinite);
}
function puntosHistorial(clave){
 const historial=historiales[clave];
 return (historial?.items||[]).map(item=>{const valor=convertirValor(clave,item?.value,historial?.unidad),timestamp=Number(item?.timestamp_utc)*1000||Date.parse(item?.datetime);return {valor,timestamp,etiqueta:item?.datetime||new Date(timestamp).toISOString()}}).filter(item=>Number.isFinite(item.valor)&&Number.isFinite(item.timestamp));
}
function crearLocalidades(){
 $("#localidades").innerHTML=Object.entries(localidades).map(([clave,item])=>'<button data-localidad="'+clave+'" class="'+(clave===localidad?"active":"")+'" aria-pressed="'+(clave===localidad)+'"><span class="locality-icon">'+item.icono+'</span><span><b>'+item.nombre+'</b><small>'+item.colegio+'</small></span><em>'+item.tipo+'</em></button>').join("");
 document.querySelectorAll("[data-localidad]").forEach(button=>button.onclick=()=>seleccionarLocalidad(button.dataset.localidad));
}
function crearCategorias(){
 $("#research-categories").innerHTML=Object.entries(categorias).map(([clave,item])=>'<button type="button" data-categoria="'+clave+'" class="'+(clave===categoriaActiva?"active":"")+'" style="--category-color:'+grupos[clave].color+'" aria-controls="grafico-'+clave+'" aria-pressed="'+(clave===categoriaActiva)+'"><span>'+item.icono+'</span><b>'+item.etiqueta+'</b></button>').join("");
 document.querySelectorAll("[data-categoria]").forEach(button=>button.onclick=()=>seleccionarCategoria(button.dataset.categoria));
}
function clavesGrupo(nombre){const grupo=grupos[nombre],modo=modos[nombre];return modo==="all"||nombre==="temperatura"&&modo==="temperatura_todas"?grupo.claves:[modo]}
function seriesGrupo(nombre){return clavesGrupo(nombre).map(clave=>({valores:valoresHistorial(clave),color:sensores[clave].color}))}
function estadoGrafico(nombre){
 const claves=clavesGrupo(nombre),estados=claves.map(clave=>estadosHistorial[clave]||"cargando"),disponibles=claves.filter(clave=>valoresHistorial(clave).length);
 if(estados.includes("cargando"))return {tipo:"cargando",texto:"Cargando historial real…"};
 if(disponibles.length)return {tipo:"ok",texto:"Historial real · "+horasPeriodo[periodo]+" horas"};
 if(estados.includes("no_disponible"))return {tipo:"error",texto:"No fue posible cargar el historial"};
 if(estados.includes("sin_asociacion"))return {tipo:"vacio",texto:"Esta variable aún no tiene un sensor asociado"};
 return {tipo:"vacio",texto:"El sensor asociado no tiene mediciones en este periodo"};
}
function tarjetaCrecimiento(grupo){
 const historial=historiales.altura_planta,items=(historial?.items||[]).map(item=>({fecha:String(item.datetime).slice(0,10),altura_promedio_cm:Number(item.value),plantas_medidas:item.plantas_medidas||0})),ultimo=items.at(-1),estado=estadoGrafico("crecimiento");
 const resumen=ultimo?'<div class="growth-summary"><div><small>Último promedio</small><strong>'+ultimo.altura_promedio_cm.toLocaleString("es-CL",{maximumFractionDigits:2})+' <span>cm</span></strong></div><div><small>Fecha de última medición</small><b>'+ultimo.fecha+'</b></div><div><small>Plantas medidas</small><b>'+ultimo.plantas_medidas+'</b></div></div>':"";
 const grafico=items.length?svgGraficoAltura(items):'<div class="growth-empty">'+estado.texto+'</div>';
 return '<article id="grafico-crecimiento" class="chart-card growth-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls"><button class="active growth-only" type="button" aria-pressed="true">Altura promedio</button><span>cm</span></div></header><h3>Altura promedio de las plantas</h3><div class="chart-state '+estado.tipo+'">'+estado.texto+'</div>'+resumen+'<div class="chart-wrap">'+grafico+'</div></article>';
}
function tarjetaTemperaturaAgua(grupo,controles){
 const historial=historiales.temperatura_agua,items=(historial?.items||[]).map(item=>({fecha:String(item.datetime).slice(0,10),valor:Number(item.value)})),estado=estadoGrafico("temperatura"),grafico=items.length?svgGraficoTemperaturaAgua(items):'<div class="growth-empty">'+estado.texto+'</div>';
 return '<article id="grafico-temperatura" class="chart-card water-temperature-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls temperature-controls">'+controles+'<span>°C</span></div></header><h3>Temperatura del agua del estanque</h3><div class="chart-state '+estado.tipo+'">'+estado.texto+'</div><div class="chart-wrap">'+grafico+'</div></article>';
}
function tarjetaTemperaturas(grupo,controles){
 const nombres={temperatura_aire:"Aire",temperatura_tierra:"Tierra",temperatura_bajo_tierra:"Bajo tierra",temperatura_agua:"Agua"},series=grupos.temperatura.claves.map(clave=>({clave,nombre:nombres[clave],color:sensores[clave].color,puntos:puntosHistorial(clave)})),tieneDatos=series.some(serie=>serie.puntos.length),faltantes=series.filter(serie=>!serie.puntos.length).map(serie=>serie.nombre),cargando=series.some(serie=>(estadosHistorial[serie.clave]||"cargando")==="cargando");
 const estado=cargando?{tipo:"cargando",texto:"Cargando temperaturas del huerto…"}:!tieneDatos?{tipo:"vacio",texto:"No hay temperaturas disponibles en este periodo"}:faltantes.length?{tipo:"vacio",texto:"Sin datos disponibles: "+faltantes.join(", ")}:{tipo:"ok",texto:"Comparación de las temperaturas disponibles"};
 const leyenda='<div class="temperature-legend">'+series.map(serie=>'<span class="'+(!serie.puntos.length?"missing":"")+'"><i style="--series-color:'+serie.color+'"></i>'+serie.nombre+'</span>').join("")+'</div>',grafico=tieneDatos?svgGraficoTemperaturas(series):'<div class="growth-empty">'+estado.texto+'</div>';
 return '<article id="grafico-temperatura" class="chart-card all-temperatures-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls temperature-controls">'+controles+'<span>°C</span></div></header><h3>Comparación de temperaturas del huerto</h3><div class="chart-state '+estado.tipo+'">'+estado.texto+'</div>'+leyenda+'<div class="chart-wrap">'+grafico+'</div></article>';
}
function crearGraficos(){
 $("#charts").innerHTML=Object.entries(grupos).map(([nombre,grupo])=>{if(nombre==="crecimiento")return tarjetaCrecimiento(grupo);const modo=modos[nombre],todas=nombre==="temperatura"&&modo==="temperatura_todas",base=sensores[modo==="all"||todas?grupo.claves[0]:modo],estado=estadoGrafico(nombre),controles=grupo.claves.map((clave,indice)=>'<button data-grupo="'+nombre+'" data-modo="'+clave+'" class="'+(modo===clave?"active":"")+'" title="'+(sensores[clave].nombreCompleto||sensores[clave].nombre)+'">'+grupo.botones[indice]+'</button>').join("")+(nombre==="temperatura"?'<button data-grupo="temperatura" data-modo="temperatura_todas" class="'+(modo==="temperatura_todas"?"active":"")+'" title="Todas las temperaturas">Todas</button>':nombre!=="agua"?'<button data-grupo="'+nombre+'" data-modo="all" class="'+(modo==="all"?"active":"")+'" title="Comparar">📈</button>':"");if(nombre==="temperatura"&&modo==="temperatura_agua")return tarjetaTemperaturaAgua(grupo,controles);if(todas)return tarjetaTemperaturas(grupo,controles);const series=seriesGrupo(nombre),tieneDatos=series.some(serie=>serie.valores.length),grafico=tieneDatos?svgGrafico(series,periodo,base.min,base.max,modo==="all"?null:base.ideal,nombre==="temperatura"?"°":nombre==="humedad"?"%":""):'<div class="growth-empty">'+estado.texto+'</div>',subtitulo=nombre==="temperatura"?'<h3 class="temperature-variable-title">'+base.nombre+'</h3>':"";return '<article id="grafico-'+nombre+'" class="chart-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls '+(nombre==="temperatura"?"temperature-controls":"")+'">'+controles+'<span>'+base.unidad+'</span></div></header>'+subtitulo+'<div class="chart-state '+estado.tipo+'">'+estado.texto+'</div><div class="chart-wrap">'+grafico+'</div></article>'}).join("");
 document.querySelectorAll("[data-modo]").forEach(button=>button.onclick=()=>seleccionarModo(button.dataset.grupo,button.dataset.modo));
}
function actualizar(){const loc=localidades[localidad];$("#explore-label").textContent="🔎 Exploración en vivo · "+loc.nombre;$("#school-context").textContent="📍 "+colegioActual();$("#history-label").textContent="▦ Historial del huerto · "+loc.nombre;$("#history-school").textContent="📍 "+colegioActual()+" · Compara los periodos y descubre cómo responde nuestra planta.";crearLocalidades();crearCategorias();renderEducationalState();crearGraficos()}
async function cargarHistorialClaves(claves,ciclo){
 const consultas=[...new Set(claves)];consultas.forEach(clave=>estadosHistorial[clave]="cargando");crearGraficos();
 await Promise.all(consultas.map(async clave=>{try{const data=await fetchHistorialEducativo(localidad,clave,horasPeriodo[periodo],60);if(ciclo!==cicloCarga)return;historiales[clave]=data;estadosHistorial[clave]=data?.estado||"sin_datos"}catch{if(ciclo!==cicloCarga)return;historiales[clave]={items:[]};estadosHistorial[clave]="no_disponible"}}));if(ciclo===cicloCarga)crearGraficos();
}
function clavesGraficosVisibles(){return Object.keys(grupos).flatMap(clavesGrupo)}
function seleccionarCategoria(categoria){categoriaActiva=categoria;crearCategorias();document.getElementById("grafico-"+categoria)?.scrollIntoView({behavior:"smooth",block:"start"})}
async function seleccionarModo(grupo,modo){modos[grupo]=modo;crearGraficos();await cargarHistorialClaves(clavesGrupo(grupo),cicloCarga)}
async function cargar(){
 const ciclo=++cicloCarga,localidadSolicitada=localidad,nombreLocalidad=localidades[localidadSolicitada].nombre;dashboard=estadoInicial();colegioId=null;historiales={};estadosHistorial={};document.querySelectorAll(".refresh").forEach(button=>{button.disabled=true;button.textContent="Actualizando…"});$("#source").textContent="● Cargando datos reales…";actualizar();anunciarCarteles("Cargando datos de "+nombreLocalidad);
 let anuncioFinal="Datos de "+nombreLocalidad+" actualizados";
 try{const data=await fetchUltimasEducativas(localidadSolicitada);if(ciclo!==cicloCarga||localidadSolicitada!==localidad)return;dashboard=data||estadoInicial("no_disponible");colegioId=dashboard.items?.find(item=>item.colegio_id)?.colegio_id||null;const reales=dashboard.items?.filter(item=>item.estado==="ok").length||0;$("#source").textContent=reales?"● Conectado a FastAPI · "+reales+" mediciones reales":"● Conectado a FastAPI · sin mediciones disponibles"}
 catch{if(ciclo!==cicloCarga||localidadSolicitada!==localidad)return;dashboard=estadoInicial("no_disponible");anuncioFinal="No fue posible conectar con el servidor";$("#source").textContent="● FastAPI no disponible"}
 finally{if(ciclo===cicloCarga&&localidadSolicitada===localidad){actualizar();anunciarCarteles(anuncioFinal);await cargarHistorialClaves(clavesGraficosVisibles(),ciclo);document.querySelectorAll(".refresh").forEach(button=>{button.disabled=false;button.textContent="↻ Actualizar datos"})}}
}
function seleccionarLocalidad(clave){localidad=clave;colegioId=null;dashboard=estadoInicial();historiales={};estadosHistorial={};actualizar();cargar()}
document.querySelectorAll(".refresh").forEach(button=>button.onclick=cargar);
document.querySelectorAll("[data-period]").forEach(button=>button.onclick=async()=>{periodo=button.dataset.period;document.querySelectorAll("[data-period]").forEach(item=>item.classList.toggle("active",item===button));const ciclo=++cicloCarga;historiales={};estadosHistorial={};actualizar();await cargarHistorialClaves(clavesGraficosVisibles(),ciclo)});
crearCartelesVisuales();dashboard=estadoInicial();actualizar();cargar();
